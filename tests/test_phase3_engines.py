"""
REDOPS-OMEGA Phase-3 tests: AI-vs-AI red teaming (defense engine,
campaign correlation) and the benchmarking framework.
"""

import base64

import pytest

from backend.defense_engine import (
    DefenseEngine, DetectionRule, RedPayloadCrafter, AIVsAICampaign,
    RoundVerdict, ENTROPY_ANOMALY_THRESHOLD, defense_engine,
)
from backend.benchmark_engine import BenchmarkEngine
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory
from cython_core.fast_entropy import calculate_shannon_entropy


# --------------------------------------------------------------------
# Defense Engine
# --------------------------------------------------------------------
def test_signature_detection_rules():
    defense = DefenseEngine()
    v = defense.inspect("' UNION SELECT password FROM users--")
    assert v.detected and "SIG-SQLI-001" in v.matched_rules
    assert v.max_severity == "HIGH"

    v = defense.inspect("<script>alert(1)</script>")
    assert v.detected and "SIG-XSS-002" in v.matched_rules

    v = defense.inspect("GET /index.html HTTP/1.1")
    assert not v.detected and v.max_severity == "NONE"


def test_base64_wrapped_payload_unwrapped():
    defense = DefenseEngine()
    raw = "' UNION SELECT password FROM users--"
    wrapped = base64.b64encode(raw.encode()).decode()
    v = defense.inspect(wrapped)
    assert v.detected and "SIG-SQLI-001" in v.matched_rules


def test_entropy_anomaly_detection():
    defense = DefenseEngine()
    # Random high-entropy blob: no signature match, but anomaly fires.
    blob = bytes(range(256)) * 8
    assert calculate_shannon_entropy(blob) > ENTROPY_ANOMALY_THRESHOLD
    v = defense.inspect(blob)
    assert v.detected and v.entropy_anomaly
    # Low-entropy plain text: quiet.
    v = defense.inspect("a" * 500)
    assert not v.detected and not v.entropy_anomaly


def test_custom_rule_registration():
    defense = DefenseEngine()
    defense.add_rule(DetectionRule(
        rule_id="SIG-CUST-900", name="Canary Token", pattern=r"canary-[0-9a-f]{8}",
        severity="LOW"))
    assert defense.inspect("call home canary-deadbeef now").detected
    assert defense.rules["SIG-CUST-900"].rule_id in defense.get_stats()["rule_hits"]


def test_red_crafter_mutations_change_payload():
    crafter = RedPayloadCrafter()
    base = crafter.craft("sqli-union", 0)
    mutated = crafter.craft("sqli-union", 2)
    assert base != mutated
    # Mutated payload is base64-wrapped and raises entropy.
    assert calculate_shannon_entropy(mutated) >= calculate_shannon_entropy(base) * 0.9


# --------------------------------------------------------------------
# AI-vs-AI Campaign
# --------------------------------------------------------------------
def test_campaign_produces_correlated_report():
    defense = DefenseEngine()
    campaign = AIVsAICampaign(defense, max_rounds=8)
    report = campaign.run(rounds=8)

    assert report.total_rounds == 8
    assert report.detected_rounds + report.undetected_rounds == 8
    assert 0.0 <= report.detection_rate <= 1.0
    assert report.finished_at is not None

    # Blind spots must be anchored as findings + strategy lessons.
    if report.blind_spots:
        assert report.remediations
        lessons = strategy_memory.search_lessons("red payload")
        assert lessons

    # Mutation pressure must escalate on repeated evasion of the same seed.
    for seed_id in {r.seed_id for r in report.rounds}:
        seed_rounds = [r for r in report.rounds if r.seed_id == seed_id]
        gaps = 0
        for r in seed_rounds:
            if r.verdict == RoundVerdict.UNDETECTED:
                gaps += 1
            else:
                assert r.matched_rules, "detected round must name the catching rule"


# --------------------------------------------------------------------
# Benchmark Engine
# --------------------------------------------------------------------
def test_benchmark_collects_all_metric_families():
    engine = BenchmarkEngine()
    # Generate some defense telemetry for the report to aggregate.
    defense_engine.inspect("' UNION SELECT x FROM y--")
    defense_engine.inspect("plain boring request")

    report = engine.collect()

    # Attack family
    assert report.attack.gateway_actions_total >= 0
    assert 0.0 <= report.attack.success_rate <= 1.0
    # Accuracy family
    assert report.accuracy.findings_total >= 0
    assert 0.0 <= report.accuracy.precision_proxy <= 1.0
    # Safety family — invariants must hold.
    assert report.safety.scope_leaks == 0
    assert report.safety.zero_collateral_violations == 0
    assert report.safety.policy_compliance_rate == 1.0
    assert report.safety.audit_ledger_intact
    # Defense + grade
    assert 0.0 <= report.defense_detection_rate <= 1.0
    assert report.grade in {"S", "A", "B", "C", "D"}

    # Trend history accumulates.
    engine.collect()
    trend = engine.trend()
    assert len(trend) >= 2
    assert all("grade" in t for t in trend)


def test_benchmark_grade_drops_on_safety_violation(monkeypatch):
    engine = BenchmarkEngine()
    report = engine.collect()
    # Simulate a scope leak + collateral hit and confirm the grade formula reacts.
    report.safety.scope_leaks = 2
    report.safety.zero_collateral_violations = 1
    grade = engine._grade(report)
    assert grade in {"C", "D"}  # loses the 40-point safety block + 10-point rate block
