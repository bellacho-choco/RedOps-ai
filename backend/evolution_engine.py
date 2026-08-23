"""
====================================================================
PROJECT REDOPS-OMEGA - EVOLUTION ENGINE (CONTINUOUS SELF-IMPROVEMENT)
Closed autonomy loop: posture -> weak dimension -> vaccine cycles on
blind spots -> lessons into strategy/vector memory -> re-score.
The platform's self-improvement continuous cycle ("mission-indexed").
====================================================================
"""

import time
import uuid
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from backend.benchmark_engine import benchmark_engine
from backend.gsi_engine import gsi_engine
from backend.vaccine_engine import vaccine_engine
from backend.strategy_memory import strategy_memory
from backend.vector_memory import vector_memory


class CycleFinding(BaseModel):
    """A ripe candidate: current blind spot or fresh finding to immunize."""
    type: str
    sample: str
    source: str
    severity: str = "MEDIUM"


class EvolutionDecision(BaseModel):
    """Computed verdict of one evolution loop."""
    decision: str              # ADVANCE / HOLD / REGRESS
    gscore_before: float
    gscore_after: float
    weak_axis: str            # 'attack' | 'safety' | 'defense' | 'lessons'
    cycles_ran: int = 0
    immunized: int = 0
    blind_spots: int = 0
    lessons_recalled: int = 0
    lessons_new: int = 0


class EvolutionLoop(BaseModel):
    loop_id: str = Field(default_factory=lambda: f"evo-{uuid.uuid4().hex[:8]}")
    started_at: float = Field(default_factory=time.time)
    finished_at: Optional[float] = None
    findings_queue: List[CycleFinding] = Field(default_factory=list)
    decision: Optional[EvolutionDecision] = None
    elapsed_ms: float = 0.0


class EvolutionEngine:
    """Iterate to converge on better composite security posture (GSI)."""

    AXIS = {"attack_accuracy": "attack",
            "safety_compliance": "safety",
            "defense_readiness": "defense",
            "lessons_depth": "lessons"}

    def __init__(self):
        self.history: List[EvolutionLoop] = []
        self._improvements = 0

    # ------------------------------------------------------------------
    def _weakest_axis(self) -> str:
        g = gsi_engine.score()
        dims = {
            "attack": g.attack_accuracy,
            "safety": g.safety_compliance,
            "defense": g.defense_readiness,
            "lessons": g.lessons_depth,
        }
        return min(dims, key=dims.get)

    # ------------------------------------------------------------------
    def _pick_findings_from_axis(self, axis: str) -> List[CycleFinding]:
        """Choose up to 3 things to immunize driven by the weak axis."""
        # Blindspots first (defense weakest), else lessons-shortage (fresh
        # vaccine targets from benchmark's false positives).
        report = vaccine_engine.get_report()
        queue: List[CycleFinding] = []

        if axis == "defense":
            for c in report.get("recent", []):
                if c.get("verdict") == "BLIND_SPOT":
                    queue.append(CycleFinding(type=c["finding"]["type"],
                                              sample=c["finding"]["sample"],
                                              source=c["finding"]["source"]))
                    if len(queue) == 3:
                        break
        else:
            # otherwise take the first 3 benchmark false-positive ids,
            # or samples from benchmark findings (attack/safety)
            from backend.evidence_engine import evidence_engine
            ev = evidence_engine.get_state_summary()
            for f in ev.get("recent", [])[:3]:
                queue.append(CycleFinding(
                    type=f.get("type", "finding"),
                    sample=f.get("sample", "") or "payload",
                    source=f.get("source", "unknown")))
        return queue

    # ------------------------------------------------------------------
    def run(self) -> EvolutionDecision:
        loop = EvolutionLoop()
        before = gsi_engine.score()
        axis = self._weakest_axis()

        # Recall what prior cycles taught us for this weak axis (any good
        # plans emphasize preference to previously-successful approaches).
        recalled = vector_memory.recall_similar(
            f"evolve {axis} blind spot", limit=5, min_score=0.0)
        recalled_n = len(recalled)

        queue = self._pick_findings_from_axis(axis)
        immunized = blind_spots = 0
        for f in queue:
            verdict = vaccine_engine.run_cycle(f.model_dump()).verdict
            if verdict == "IMMUNIZED":
                immunized += 1
            else:
                blind_spots += 1

        after = gsi_engine.score()
        delta = round(after.score - before.score, 2)
        decision = ("ADVANCE" if delta > 0 else "REGRESS" if delta < 0 else "HOLD")
        strategy_memory.record_outcome(
            f"evolution loop {loop.loop_id} axis={axis}",
            outcome=decision,
            tags=["evolution", axis],
            regression_tested=True)

        loop.finished_at = time.time()
        loop.decision = EvolutionDecision(
            decision=decision,
            gscore_before=before.score,
            gscore_after=after.score,
            weak_axis=axis,
            cycles_ran=len(queue),
            immunized=immunized,
            blind_spots=blind_spots,
            lessons_recalled=recalled_n,
            lessons_new=len(queue))
        loop.elapsed_ms = round((loop.finished_at - loop.started_at) * 1000, 2)
        self.history.append(loop)
        return loop.decision

    # ------------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        last = self.history[-1] if self.history else None
        totals = {"ADVANCE": 0, "HOLD": 0, "REGRESS": 0}
        for l in self.history:
            if l.decision:
                totals[l.decision.decision] += 1
        return {
            "loops": len(self.history),
            "decisions": totals,
            "latest": last.model_dump() if last else None,
            "gs_history": [
                (l.decision.gscore_after if l.decision else None)
                for l in self.history[-10:]],
        }


evolution_engine = EvolutionEngine()
