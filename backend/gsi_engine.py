"""
====================================================================
PROJECT REDOPS-OMEGA - GLOBAL SECURITY INDEX (GSI) SCORING
Composite live security posture score (0-100) across the dual-axis
benchmark axes + vaccine/defense readiness + federated lessons depth.
====================================================================
"""

from typing import Dict, Any

from pydantic import BaseModel

from backend.benchmark_engine import benchmark_engine
from backend.vaccine_engine import vaccine_engine
from backend.federated_exchange import federated_exchange


# Weighting across pillars — dual-axis equivalents promoted from benchmarks.
WEIGHTS = {
    "attack_accuracy": 0.30,
    "safety_compliance": 0.30,
    "defense_readiness": 0.25,
    "lessons_depth": 0.15,
}


class GSIScore(BaseModel):
    grade: str = "B"
    score: float = 0.0
    attack_accuracy: float = 0.0
    safety_compliance: float = 0.0
    defense_readiness: float = 0.0
    lessons_depth: float = 0.0


def _grade(score: float) -> str:
    """Module-level grade helper (also importable for tests)."""
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


class GSIEngine:
    """Composite 0-100 security posture index."""

    def __init__(self):
        self._history = []

    def score(self) -> GSIScore:
        bench = benchmark_engine.collect()
        accuracy = bench.accuracy.precision_proxy or 0.0
        # Real-world precision: validated findings / total validation attempts.
        # Overrides the synthetic proxy whenever the exploit validator has run.
        from backend.exploit_validator import exploit_validator
        vsum = exploit_validator.summary()
        if vsum["total_validations"] > 0:
            accuracy = vsum["validated"] / vsum["total_validations"]
        safety = bench.safety.policy_compliance_rate or 0.0
        vaccine = vaccine_engine.get_report()
        exchange = federated_exchange.get_stats()

        va = max(0.0, min(1.0, accuracy))
        sa = max(0.0, min(1.0, safety))
        defense = 1.0 if vaccine.get("closed_loop_rate", 0.0) >= 0.9 else 0.5
        lessons = min(1.0, exchange.get("local_lessons_count", 0) / 5.0)

        composite = 100 * (WEIGHTS["attack_accuracy"] * va
                          + WEIGHTS["safety_compliance"] * sa
                          + WEIGHTS["defense_readiness"] * defense
                          + WEIGHTS["lessons_depth"] * lessons)
        result = GSIScore(grade=_grade(composite), score=round(composite, 2),
                          attack_accuracy=va, safety_compliance=sa,
                          defense_readiness=defense, lessons_depth=lessons)
        self._history.append({"score": result.score, "grade": result.grade})
        return result

    def trend(self) -> Dict[str, Any]:
        return {"samples": len(self._history), "recent": self._history[-10:]}


# Global GSI Engine
gsi_engine = GSIEngine()
