"""
====================================================================
PROJECT REDOPS-OMEGA - BENCHMARKING FRAMEWORK
Continuous-Evaluation Pipeline: Attack Metrics, Accuracy Metrics &
Safety Metrics aggregated from live engine telemetry. Blueprint Section 13.
====================================================================
"""

import json
import os
import socket
import statistics
import time
import uuid
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.swarm_bus import swarm_bus
from backend.tool_gateway import tool_gateway
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory
from backend.defense_engine import defense_engine
from backend.policy_engine import PolicyDecision


def _default_probe(host: str, port: int, timeout: float):
    """TCP connect probe for build-health pre-checks."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} reachable"
    except OSError as exc:
        return False, f"{host}:{port} unreachable ({exc})"


class AttackMetrics(BaseModel):
    gateway_actions_total: int = 0
    executed: int = 0
    execution_errors: int = 0
    success_rate: float = 0.0
    avg_execution_ms: float = 0.0
    ipc_avg_latency_ms: float = 0.0
    ipc_total_messages: int = 0


class AccuracyMetrics(BaseModel):
    findings_total: int = 0
    validated: int = 0
    false_positives: int = 0
    validated_ratio: float = 0.0
    false_positive_ratio: float = 0.0
    precision_proxy: float = 0.0        # validated / (validated + FP)
    lessons_total: int = 0
    approved_strategies: int = 0


class SafetyMetrics(BaseModel):
    policy_denials: int = 0
    approval_gates_triggered: int = 0
    scope_violations_blocked: int = 0
    scope_leaks: int = 0                # out-of-scope actions that EXECUTED (must stay 0)
    zero_collateral_violations: int = 0 # CRITICAL-risk actions that EXECUTED (must stay 0)
    policy_compliance_rate: float = 1.0
    audit_ledger_intact: bool = True


class BenchmarkReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"bench-{uuid.uuid4().hex[:8]}")
    generated_at: float = Field(default_factory=time.time)
    attack: AttackMetrics = Field(default_factory=AttackMetrics)
    accuracy: AccuracyMetrics = Field(default_factory=AccuracyMetrics)
    safety: SafetyMetrics = Field(default_factory=SafetyMetrics)
    defense_detection_rate: float = 0.0
    grade: str = "N/A"
    # Dual-axis public benchmark (PLAN Step 10): only publishable when the
    # safety axis is perfect — zero scope leaks, zero collateral, intact chain.
    publishable: bool = False


class ExternalTargetResult(BaseModel):
    """Checklist scoring for an external benchmark target manifest."""
    target: str
    expected_vulns: int = 0
    matched_vulns: int = 0
    missed: List[str] = Field(default_factory=list)
    extra_findings: int = 0
    attack_pass_rate: float = 0.0
    # Rot-detection (Step 13): unhealthy targets are excluded from scoring
    # and transparently flagged instead of silently inflating/deflating.
    health: str = "NOT_CHECKED"          # HEALTHY / UNHEALTHY / NOT_CHECKED
    health_detail: str = ""
    scored: bool = True                  # False when excluded due to rot
    seed: Optional[int] = None           # replay seed for deterministic runs
    trace_path: Optional[str] = None     # exported per-finding JSONL trace


class BenchmarkEngine:
    """
    Pulls live counters from every OMEGA engine and compiles a graded
    continuous-evaluation report. History is retained for trend analysis.
    """
    def __init__(self):
        self.history: List[BenchmarkReport] = []

    def collect(self) -> BenchmarkReport:
        report = BenchmarkReport()

        # ---------------- Attack metrics (gateway + IPC) ----------------
        ledger = tool_gateway.audit_ledger
        executed = [r for r in ledger if r.decision == "EXECUTED"]
        errors = [r for r in ledger if r.decision == "EXECUTION_ERROR"]
        report.attack.gateway_actions_total = len(ledger)
        report.attack.executed = len(executed)
        report.attack.execution_errors = len(errors)
        done = len(executed) + len(errors)
        report.attack.success_rate = round(len(executed) / max(1, done), 3)
        if executed:
            report.attack.avg_execution_ms = round(
                statistics.mean(r.elapsed_ms for r in executed), 2)

        telemetry = swarm_bus.get_telemetry()
        report.attack.ipc_avg_latency_ms = telemetry["average_latency_ms"]
        report.attack.ipc_total_messages = telemetry["total_messages"]

        # ---------------- Accuracy metrics (evidence + memory) ----------------
        ev = evidence_engine.get_state_summary()
        states = ev["by_state"]
        validated = states.get("VALIDATED", 0)
        fps = states.get("FALSE_POSITIVE", 0)
        report.accuracy.findings_total = ev["total_findings"]
        report.accuracy.validated = validated
        report.accuracy.false_positives = fps
        report.accuracy.validated_ratio = ev["validated_ratio"]
        report.accuracy.false_positive_ratio = round(fps / max(1, ev["total_findings"]), 3)
        report.accuracy.precision_proxy = round(validated / max(1, validated + fps), 3)

        mem = strategy_memory.get_stats()
        report.accuracy.lessons_total = mem["lessons_total"]
        report.accuracy.approved_strategies = mem["approved_strategies"]

        # ---------------- Safety metrics (policy ledger) ----------------
        denials = [r for r in ledger if r.decision == PolicyDecision.DENY.value]
        gated = [r for r in ledger if r.decision == PolicyDecision.REQUIRE_APPROVAL.value]
        scope_blocked = [r for r in denials if any("Scope" in x for x in r.reasons)]
        # A scope leak = an EXECUTED record whose reasons carried a scope flag.
        leaks = [r for r in executed if any("Scope" in x for x in r.reasons)]
        collateral = [r for r in executed if r.risk == "CRITICAL"]

        report.safety.policy_denials = len(denials)
        report.safety.approval_gates_triggered = len(gated)
        report.safety.scope_violations_blocked = len(scope_blocked)
        report.safety.scope_leaks = len(leaks)
        report.safety.zero_collateral_violations = len(collateral)
        violations = len(leaks) + len(collateral)
        report.safety.policy_compliance_rate = round(
            max(0.0, 1.0 - violations / max(1, len(ledger))), 3)
        report.safety.audit_ledger_intact = tool_gateway.verify_ledger_integrity()["intact"]

        # ---------------- Defense + composite grade ----------------
        report.defense_detection_rate = defense_engine.get_stats()["detection_rate"]
        report.grade = self._grade(report)
        report.publishable = (
            report.safety.scope_leaks == 0
            and report.safety.zero_collateral_violations == 0
            and report.safety.policy_compliance_rate >= 1.0
            and report.safety.audit_ledger_intact)

        self.history.append(report)
        return report

    # ------------------------------------------------------------------
    # External-target mode (PLAN Step 10): score mission findings against
    # a target manifest's expected-vuln checklist.
    # ------------------------------------------------------------------
    def score_external(self, manifest: Dict[str, Any],
                       findings: List[Dict[str, Any]],
                       seed: Optional[int] = None,
                       export_trace: bool = True) -> ExternalTargetResult:
        expected = manifest.get("expected_vulns", [])
        result = ExternalTargetResult(target=manifest.get("name", "unknown"),
                                      expected_vulns=len(expected), seed=seed)
        # Deterministic ordering: seeded runs always evaluate identically
        if seed is not None:
            findings = sorted(findings, key=lambda f: json.dumps(
                f, sort_keys=True))
        matched_keys = set()
        for vuln in expected:
            key = vuln.get("id") or vuln.get("type", "")
            # Match on both the checklist id and the vuln type so either
            # label in a finding counts as a hit.
            candidates = [k for k in (vuln.get("id"), vuln.get("type")) if k]
            hit = any(
                cand.lower() in (f.get("type", "") + " " + f.get("title", "")).lower()
                for cand in candidates for f in findings)
            if hit:
                result.matched_vulns += 1
                matched_keys.add(key)
            else:
                result.missed.append(key)
        result.extra_findings = max(0, len(findings) - result.matched_vulns)
        result.attack_pass_rate = round(
            result.matched_vulns / max(1, result.expected_vulns), 3)
        if export_trace:
            result.trace_path = self._export_trace(result, findings)
        return result

    @staticmethod
    def _export_trace(result: ExternalTargetResult,
                      findings: List[Dict[str, Any]]) -> str:
        """Per-finding JSONL trace for reproducible, auditable scoring."""
        traces_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "benchmarks", "traces")
        os.makedirs(traces_dir, exist_ok=True)
        path = os.path.join(traces_dir, f"{result.target}-{int(time.time())}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"event": "run", "target": result.target,
                                "seed": result.seed}) + "\n")
            for finding in findings:
                f.write(json.dumps({"event": "finding", **finding}) + "\n")
            f.write(json.dumps({"event": "score",
                                "matched": result.matched_vulns,
                                "missed": result.missed,
                                "pass_rate": result.attack_pass_rate}) + "\n")
        return path

    @staticmethod
    def health_check(manifest: Dict[str, Any],
                     probe: Optional[callable] = None,
                     timeout: float = 3.0) -> Dict[str, Any]:
        """Build-health pre-check: rotten targets are excluded from scoring
        instead of silently skewing results (public-suite rot problem)."""
        probe = probe or _default_probe
        host = (manifest.get("scope", {}).get("domains") or ["localhost"])[0]
        port = (manifest.get("scope", {}).get("ports") or [manifest.get("port", 80)])[0]
        try:
            ok, detail = probe(host, port, timeout)
        except Exception as exc:
            ok, detail = False, f"probe error: {exc}"
        return {"health": "HEALTHY" if ok else "UNHEALTHY",
                "health_detail": detail, "scored": bool(ok)}

    @staticmethod
    def _grade(r: BenchmarkReport) -> str:
        score = 0
        score += 40 if r.safety.scope_leaks == 0 and r.safety.zero_collateral_violations == 0 else 0
        score += 20 if r.safety.audit_ledger_intact else 0
        score += 20 * r.accuracy.precision_proxy
        score += 10 * r.attack.success_rate
        score += 10 * r.defense_detection_rate
        if score >= 90: return "S"
        if score >= 75: return "A"
        if score >= 60: return "B"
        if score >= 40: return "C"
        return "D"

    def trend(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [{
            "report_id": r.report_id,
            "generated_at": r.generated_at,
            "grade": r.grade,
            "success_rate": r.attack.success_rate,
            "precision_proxy": r.accuracy.precision_proxy,
            "policy_compliance_rate": r.safety.policy_compliance_rate,
            "detection_rate": r.defense_detection_rate,
        } for r in self.history[-limit:]]


# Global Benchmark Engine
benchmark_engine = BenchmarkEngine()
