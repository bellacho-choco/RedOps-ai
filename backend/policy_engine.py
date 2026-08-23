"""
====================================================================
PROJECT REDOPS-OMEGA - POLICY & AUTHORIZATION ENGINE
Risk Classification, Zero-Collateral Enforcement, Capability Tokens
& Cryptographic Human Approval Gates. Blueprint Section 10.
====================================================================
"""

import hashlib
import hmac
import re
import secrets
import time
from enum import Enum
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Payload patterns that must never run without a human signature.
HAZARDOUS_PATTERNS = [
    (re.compile(r"\brm\s+-[rf]{1,2}\b", re.I), "recursive deletion"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"), "fork bomb"),
    (re.compile(r"\bmkfs\b|\bformat\b.*\b(drive|disk)\b", re.I), "disk destruction"),
    (re.compile(r"\b(shutdown|reboot|poweroff|halt)\b", re.I), "system power action"),
    (re.compile(r"\b(dd\s+if=).*(of=/dev/)", re.I), "raw disk write"),
    (re.compile(r"\b(mimikatz|sekurlsa|lsadump|dcsync)\b", re.I), "credential dumping"),
    (re.compile(r"\b(ms17-010|eternalblue)\b", re.I), "kernel-level exploit (zero-collateral quarantine)"),
    (re.compile(r"\b(psexec|wmiexec|smbexec)\b", re.I), "lateral movement exec"),
    (re.compile(r"\bDROP\s+TABLE\b|\bTRUNCATE\b", re.I), "destructive SQL"),
    (re.compile(r"\biptables\s+-F\b|\bnetsh\b.*\bfirewall\b.*\boff\b", re.I), "firewall tampering"),
]

# MITRE techniques that always require a human approval gate.
HIGH_IMPACT_TECHNIQUES = {
    "T1003": "OS Credential Dumping",
    "T1021": "Remote Services (lateral movement)",
    "T1485": "Data Destruction",
    "T1486": "Data Encrypted for Impact",
    "T1498": "Network Denial of Service",
    "T1529": "System Shutdown/Reboot",
}

RISK_ORDER = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]

# Role-based tool authorization matrix: which hero may invoke which tool class.
AGENT_TOOL_MATRIX: Dict[str, List[str]] = {
    "OVERLORD-PRIME": ["*"],  # commander holds all keys, still policy-checked
    "SPECTRE-RECON": ["port_scan", "dns_enum", "osint_lookup", "banner_grab", "http_probe"],
    "NEXUS-CYPHER": ["graph_query", "graph_ingest", "path_solve"],
    "VORTEX-EXPLOIT": ["http_probe", "sast_scan", "cve_lookup", "exploit_dryrun", "fuzzer"],
    "CIPHER-MORPH": ["entropy_scan", "sast_scan", "sandbox_exec", "payload_mutate"],
    "CHRONO-DEBRIEF": ["evidence_read", "report_gen", "graph_query", "detector_query"],
}


class ActionRequest(BaseModel):
    agent: str
    tool: str
    target: str
    params: Dict[str, Any] = Field(default_factory=dict)
    mitre_techniques: List[str] = Field(default_factory=list)
    declared_risk: RiskLevel = RiskLevel.LOW


class PolicyVerdict(BaseModel):
    decision: PolicyDecision
    risk: RiskLevel
    reasons: List[str] = Field(default_factory=list)
    approval_id: Optional[str] = None
    evaluated_at: float = Field(default_factory=time.time)


class ApprovalTicket(BaseModel):
    approval_id: str
    action: ActionRequest
    reason: str
    status: str = "PENDING"     # PENDING | APPROVED | REJECTED
    created_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 900)  # 15 min


class CapabilityToken:
    """
    HMAC-signed token issued by OVERLORD-PRIME. Binds agent + tool + mission
    so a token minted for recon cannot be replayed for exploitation.
    """
    def __init__(self, secret: Optional[bytes] = None):
        self._secret = secret or secrets.token_bytes(32)

    def issue(self, agent: str, tool: str, mission_id: str, ttl_s: int = 3600) -> str:
        expiry = int(time.time()) + ttl_s
        payload = f"{agent}|{tool}|{mission_id}|{expiry}"
        sig = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}|{sig}"

    def verify(self, token: str, agent: str, tool: str, mission_id: str) -> bool:
        try:
            t_agent, t_tool, t_mission, t_expiry, t_sig = token.rsplit("|", 4)
        except ValueError:
            return False
        payload = f"{t_agent}|{t_tool}|{t_mission}|{t_expiry}"
        expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, t_sig):
            return False
        if int(t_expiry) < int(time.time()):
            return False
        return t_agent == agent and (t_tool == tool or t_tool == "*") and t_mission == mission_id


class PolicyEngine:
    """
    Sits directly above the Tool Gateway. Every agent action is evaluated
    for risk, zero-collateral compliance and human-approval requirements.
    """
    def __init__(self, token_issuer: Optional[CapabilityToken] = None):
        self.token_issuer = token_issuer or CapabilityToken()
        self.approvals: Dict[str, ApprovalTicket] = {}
        self.decision_log: List[PolicyVerdict] = []

    def classify_risk(self, action: ActionRequest) -> tuple[RiskLevel, List[str]]:
        risk = action.declared_risk
        reasons: List[str] = []
        payload_text = f"{action.tool} {action.target} {action.params}"

        for pattern, label in HAZARDOUS_PATTERNS:
            if pattern.search(payload_text):
                risk = RiskLevel.CRITICAL
                reasons.append(f"hazardous pattern detected: {label}")

        for tech in action.mitre_techniques:
            if tech in HIGH_IMPACT_TECHNIQUES:
                if RISK_ORDER.index(risk) < RISK_ORDER.index(RiskLevel.HIGH):
                    risk = RiskLevel.HIGH
                reasons.append(f"high-impact MITRE technique {tech}: {HIGH_IMPACT_TECHNIQUES[tech]}")

        return risk, reasons

    def evaluate(self, action: ActionRequest, roe: Optional[Any] = None) -> PolicyVerdict:
        risk, reasons = self.classify_risk(action)

        # Caller identity: is this agent allowed to hold this tool at all?
        allowed = AGENT_TOOL_MATRIX.get(action.agent.upper(), [])
        if "*" not in allowed and action.tool not in allowed:
            verdict = PolicyVerdict(
                decision=PolicyDecision.DENY, risk=risk,
                reasons=[f"Agent '{action.agent}' is barred from tool '{action.tool}'"] + reasons,
            )
            self.decision_log.append(verdict)
            return verdict

        disruptive = risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        if roe is not None:
            if disruptive and not getattr(roe, "disruptive_actions_allowed", False):
                reasons.append("RoE forbids disruptive actions")
            if risk == RiskLevel.CRITICAL and getattr(roe, "zero_collateral_policy", True):
                verdict = PolicyVerdict(
                    decision=PolicyDecision.DENY, risk=risk,
                    reasons=["Zero-collateral policy: CRITICAL-risk action quarantined"] + reasons,
                )
                self.decision_log.append(verdict)
                return verdict

        if disruptive:
            ticket = ApprovalTicket(
                approval_id=f"appr-{secrets.token_hex(4)}",
                action=action,
                reason="; ".join(reasons) or "high-risk action requires human gate",
            )
            self.approvals[ticket.approval_id] = ticket
            verdict = PolicyVerdict(
                decision=PolicyDecision.REQUIRE_APPROVAL, risk=risk,
                reasons=reasons, approval_id=ticket.approval_id,
            )
        else:
            verdict = PolicyVerdict(decision=PolicyDecision.ALLOW, risk=risk, reasons=reasons)

        self.decision_log.append(verdict)
        return verdict

    def approve(self, approval_id: str, operator: str) -> Optional[ApprovalTicket]:
        ticket = self.approvals.get(approval_id)
        if ticket and ticket.status == "PENDING" and ticket.expires_at > time.time():
            ticket.status = "APPROVED"
            ticket.reason += f" | approved_by={operator}"
        return ticket

    def reject(self, approval_id: str, operator: str) -> Optional[ApprovalTicket]:
        ticket = self.approvals.get(approval_id)
        if ticket and ticket.status == "PENDING":
            ticket.status = "REJECTED"
            ticket.reason += f" | rejected_by={operator}"
        return ticket

    def is_approved(self, approval_id: str) -> bool:
        ticket = self.approvals.get(approval_id)
        return bool(ticket and ticket.status == "APPROVED" and ticket.expires_at > time.time())

    def pending_approvals(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [t.model_dump() for t in self.approvals.values()
                if t.status == "PENDING" and t.expires_at > now]


# Global Policy Engine
policy_engine = PolicyEngine()
