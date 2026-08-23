"""
====================================================================
PROJECT REDOPS-OMEGA - BENCHMARKING FRAMEWORK
Continuous-Evaluation Pipeline: Attack Metrics, Accuracy Metrics &
Safety Metrics aggregated from live engine telemetry. Blueprint Section 13.
====================================================================
"""

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

        self.history.append(report)
        return report

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
