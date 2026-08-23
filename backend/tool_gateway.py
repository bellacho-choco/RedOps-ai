"""
====================================================================
PROJECT REDOPS-OMEGA - TOOL GATEWAY
Centralized Capability-Token enforcement, Post-DNS Scope Verification,
RoE Rate-Limiting & Hash-Chained Audit Ledger. Blueprint Section 6.
====================================================================
"""

import hashlib
import ipaddress
import socket
import time
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Callable, Awaitable

from pydantic import BaseModel, Field

from backend.policy_engine import (
    policy_engine, ActionRequest, PolicyDecision, RiskLevel,
)
from backend.mission_engine import mission_engine


class AuditRecord(BaseModel):
    seq: int
    timestamp: float
    agent: str
    tool: str
    target: str
    resolved_ip: Optional[str] = None
    decision: str
    risk: str
    reasons: List[str] = Field(default_factory=list)
    approval_id: Optional[str] = None
    result_digest: Optional[str] = None
    prev_hash: str = ""
    record_hash: str = ""

    def compute_hash(self) -> str:
        body = f"{self.seq}|{self.timestamp}|{self.agent}|{self.tool}|{self.target}|{self.decision}|{self.prev_hash}"
        return hashlib.sha256(body.encode()).hexdigest()


class ToolGateway:
    """
    The single choke-point through which every agent action flows:

        Agent Request -> Capability Token check -> Policy Engine
                      -> DNS resolution -> Scope Enforcer -> RoE limits
                      -> Registered Tool Executor -> Audit Ledger
    """
    def __init__(self):
        self.policy = policy_engine
        self.executors: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {}
        self.audit_ledger: List[AuditRecord] = []
        self._last_hash = "GENESIS"
        self._rate_windows: Dict[str, deque] = defaultdict(deque)

    def register_tool(self, name: str, executor: Callable[..., Awaitable[Dict[str, Any]]]):
        self.executors[name] = executor

    # ----------------------------------------------------------------
    # RoE helpers
    # ----------------------------------------------------------------
    def _within_allowed_hours(self, roe) -> bool:
        window = getattr(roe, "allowed_hours_utc", None)
        if not window:
            return True
        try:
            start_s, end_s = window.split("-")
            now = time.gmtime()
            cur = now.tm_hour * 60 + now.tm_min
            sh, sm = map(int, start_s.split(":"))
            eh, em = map(int, end_s.split(":"))
            start, end = sh * 60 + sm, eh * 60 + em
            return start <= cur <= end if start <= end else cur >= start or cur <= end
        except (ValueError, AttributeError):
            return True

    def _check_rate(self, mission_id: str, max_qps: int) -> bool:
        now = time.time()
        window = self._rate_windows[mission_id]
        while window and now - window[0] > 1.0:
            window.popleft()
        if len(window) >= max_qps:
            return False
        window.append(now)
        return True

    @staticmethod
    def _resolve(target: str) -> Optional[str]:
        host = target.split("//")[-1].split("/")[0].split(":")[0]
        try:
            ipaddress.ip_address(host)
            return host
        except ValueError:
            pass
        try:
            return socket.gethostbyname(host)
        except (socket.gaierror, UnicodeError):
            return None

    def _audit(self, seq_extra: Dict[str, Any]) -> AuditRecord:
        record = AuditRecord(seq=len(self.audit_ledger) + 1, prev_hash=self._last_hash, **seq_extra)
        record.record_hash = record.compute_hash()
        self._last_hash = record.record_hash
        self.audit_ledger.append(record)
        return record

    # ----------------------------------------------------------------
    # Main entry point
    # ----------------------------------------------------------------
    async def execute(self, action: ActionRequest, capability_token: Optional[str] = None,
                      approval_id: Optional[str] = None) -> Dict[str, Any]:
        mission = mission_engine.get_active()
        resolved_ip = self._resolve(action.target)

        def deny(reason: str, verdict=None) -> Dict[str, Any]:
            self._audit({
                "timestamp": time.time(), "agent": action.agent, "tool": action.tool,
                "target": action.target, "resolved_ip": resolved_ip,
                "decision": PolicyDecision.DENY.value,
                "risk": (verdict.risk.value if verdict else RiskLevel.LOW.value),
                "reasons": ([reason] + (verdict.reasons if verdict else [])),
                "approval_id": approval_id,
            })
            return {"status": "DENIED", "reason": reason,
                    "reasons": ([reason] + (verdict.reasons if verdict else []))}

        # 1. Active mission required — no manifest, no weapons.
        if not mission or mission.status != "ACTIVE":
            return deny("No ACTIVE mission manifest loaded; gateway is sealed")

        roe = mission.manifest.rules_of_engagement

        # 2. Capability token binds agent+tool+mission.
        if not capability_token or not self.policy.token_issuer.verify(
            capability_token, action.agent, action.tool, mission.manifest.mission_id
        ):
            return deny("Missing or invalid capability token for agent/tool/mission binding")

        # 3. Policy Engine: identity matrix, risk class, zero-collateral.
        verdict = self.policy.evaluate(action, roe=roe)
        if verdict.decision == PolicyDecision.DENY:
            return deny("Policy engine denied action", verdict)

        if verdict.decision == PolicyDecision.REQUIRE_APPROVAL:
            if not (approval_id and self.policy.is_approved(approval_id)):
                self._audit({
                    "timestamp": time.time(), "agent": action.agent, "tool": action.tool,
                    "target": action.target, "resolved_ip": resolved_ip,
                    "decision": PolicyDecision.REQUIRE_APPROVAL.value,
                    "risk": verdict.risk.value, "reasons": verdict.reasons,
                    "approval_id": verdict.approval_id,
                })
                return {
                    "status": "PENDING_APPROVAL",
                    "approval_id": verdict.approval_id,
                    "reason": "Action gated pending human cryptographic approval",
                    "risk": verdict.risk.value,
                }

        # 4. Scope enforcement AFTER DNS resolution (redirect-safe).
        scope_check = mission.scope_enforcer.check(action.target, resolved_ip=resolved_ip)
        if not scope_check["in_scope"]:
            return deny(f"Scope violation: {scope_check['reason']}", verdict)

        # 5. Rules of Engagement: operating hours + QPS ceiling.
        if not self._within_allowed_hours(roe):
            return deny(f"Outside RoE allowed hours ({roe.allowed_hours_utc} UTC)", verdict)
        if not self._check_rate(mission.manifest.mission_id, roe.max_qps):
            return deny(f"RoE max_qps={roe.max_qps} exceeded", verdict)

        # 6. Dispatch to registered executor.
        executor = self.executors.get(action.tool)
        if not executor:
            return deny(f"No executor registered for tool '{action.tool}'", verdict)

        started = time.perf_counter()
        try:
            result = await executor(action.target, **action.params)
            status = "EXECUTED"
            digest = hashlib.sha256(repr(result).encode()).hexdigest()[:16]
        except Exception as exc:
            result = {"error": str(exc)}
            status = "EXECUTION_ERROR"
            digest = None

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        record = self._audit({
            "timestamp": time.time(), "agent": action.agent, "tool": action.tool,
            "target": action.target, "resolved_ip": resolved_ip,
            "decision": status, "risk": verdict.risk.value,
            "reasons": verdict.reasons, "approval_id": approval_id,
            "result_digest": digest,
        })
        return {
            "status": status,
            "elapsed_ms": elapsed_ms,
            "risk": verdict.risk.value,
            "audit_seq": record.seq,
            "result": result,
        }

    def verify_ledger_integrity(self) -> Dict[str, Any]:
        prev = "GENESIS"
        for rec in self.audit_ledger:
            if rec.prev_hash != prev or rec.record_hash != rec.compute_hash():
                return {"intact": False, "broken_at_seq": rec.seq}
            prev = rec.record_hash
        return {"intact": True, "records": len(self.audit_ledger)}

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [r.model_dump() for r in self.audit_ledger[-limit:]]


# Global Tool Gateway
tool_gateway = ToolGateway()
