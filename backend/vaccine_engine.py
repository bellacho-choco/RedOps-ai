"""
====================================================================
PROJECT REDOPS-OMEGA - OFFENSIVE VACCINE LOOP (BEAT #1, FLAGSHIP)
Decepticon only *planned* this. We ship it: attack -> defend -> verify
-> patch -> regression, as one closed governed cycle.

   finding -> defense rule synthesized -> attack replay vs rule
      -> undetected? mutate & escalate (max 3, circuit breaker)
      -> detected?   self-healing patch draft + regression-gated lesson

Every cycle's verdict is anchored into the Evidence Engine.
====================================================================
"""

import re
import time
import uuid
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.defense_engine import defense_engine, DetectionRule, RedPayloadCrafter
from backend.self_healing_engine import self_healing_engine
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory
from backend.vector_memory import vector_memory

MAX_MUTATION_ROUNDS = 3  # circuit breaker per Blueprint Section 14


class ReplayVerdict(BaseModel):
    mutation_round: int
    detected: bool
    matched_rules: List[str] = Field(default_factory=list)
    payload_entropy: float = 0.0
    guided_by: List[str] = Field(default_factory=list)  # lessons that shaped this round


class VaccineCycle(BaseModel):
    cycle_id: str = Field(default_factory=lambda: f"vax-{uuid.uuid4().hex[:8]}")
    finding: Dict[str, Any]
    rule: Optional[DetectionRule] = None
    replays: List[ReplayVerdict] = Field(default_factory=list)
    patch_draft_id: Optional[str] = None
    evidence_finding_id: Optional[str] = None
    verdict: str = "OPEN"          # OPEN | IMMUNIZED | BLIND_SPOT
    lesson_id: Optional[str] = None
    started_at: float = Field(default_factory=time.time)
    finished_at: Optional[float] = None
    elapsed_ms: float = 0.0


def synthesize_rule_for_finding(finding: Dict[str, Any]) -> DetectionRule:
    """Sigma-style rule from a raw finding: anchor on the payload's most
    discriminating literal token, regex-escaped (no overfit to noise)."""
    sample = finding.get("sample") or finding.get("title") or "unknown"
    tokens = [t for t in re.split(r"\W+", sample) if len(t) >= 4]
    anchor = max(tokens, key=len) if tokens else "payload"
    ftype = finding.get("type", "GENERIC").upper()
    sev = finding.get("severity", "MEDIUM")
    return DetectionRule(
        rule_id=f"VAC-{uuid.uuid4().hex[:6].upper()}",
        name=f"Vaccine auto-rule for {ftype}",
        pattern=rf"(?i){re.escape(anchor)}",
        severity=sev, mitre_technique="T1190", category="signature",
    )


class VaccineEngine:
    """Closed-loop attack/defend/verify/patch/regression orchestrator."""

    def __init__(self, defense=defense_engine, healer=self_healing_engine,
                 evidence=evidence_engine, memory=strategy_memory):
        self.defense = defense
        self.healer = healer
        self.evidence = evidence
        self.memory = memory
        self.red = RedPayloadCrafter()
        self.cycles: Dict[str, VaccineCycle] = {}

    # ----------------------------------------------------------------
    # BEAT #4: self-improving evasion — mutation strategy shaped by
    # semantically-recalled past failures before the payload is crafted.
    # ----------------------------------------------------------------
    def _guided_craft(self, finding: Dict[str, Any], base_seed: str,
                      first_round: int) -> tuple[int, List[str]]:
        """Recall past lessons for this finding class; escalate the starting
        mutation round past previously-failed rounds."""
        ftype = finding.get("type", "payload")
        recalled = vector_memory.recall_similar(
            f"vaccine blind spot {ftype} {finding.get('sample', '')[:60]}",
            limit=5, min_score=0.05)
        guided = [r["entry_id"] for r in recalled]
        failed_rounds = [r["metadata"].get("failed_round", 0) for r in recalled
                         if r.get("outcome") in ("BLIND_SPOT", "FAILURE")]
        start = max(first_round, max(failed_rounds, default=0))
        return min(start, MAX_MUTATION_ROUNDS), guided

    # ----------------------------------------------------------------
    def run_cycle(self, finding: Dict[str, Any]) -> VaccineCycle:
        started = time.perf_counter()
        cycle = VaccineCycle(finding=finding)

        # 1) Anchor the offensive finding as evidence.
        ev = self.evidence.register_finding(
            title=f"Vaccine target: {finding.get('type', 'finding')}",
            target=finding.get("source", "unknown"),
            agent="VORTEX-EXPLOIT",
            severity=finding.get("severity", "MEDIUM"))
        cycle.evidence_finding_id = ev.finding_id

        # 2) Synthesize a defense rule from the finding and install it.
        rule = synthesize_rule_for_finding(finding)
        self.defense.add_rule(rule)
        cycle.rule = rule

        # 3) Attack replay: round 0 raw payload, then guided mutation.
        sample = (finding.get("sample") or "payload").encode()
        start_round, guided = self._guided_craft(finding, "sqli-union", 1)
        detected = False
        rounds_played: List[int] = [0]
        for rnd in range(0, MAX_MUTATION_ROUNDS + 1):
            if rnd == 0:
                payload = sample
            elif rnd >= start_round:
                payload = self.red.craft("sqli-union", rnd)
            else:
                continue  # skip rounds the memory already cleared
            verdict = self.defense.inspect(payload)
            cycle.replays.append(ReplayVerdict(
                mutation_round=rnd, detected=verdict.detected,
                matched_rules=verdict.matched_rules,
                payload_entropy=verdict.entropy,
                guided_by=guided if rnd > 0 else []))
            rounds_played.append(rnd)
            if verdict.detected:
                detected = True
                break
        max_failed = max(rounds_played) if not detected else None

        # 4) Close the loop.
        if detected:
            patch = self.healer.synthesize_patch({
                "type": finding.get("type", "GENERIC"),
                "severity": finding.get("severity", "MEDIUM"),
                "source": finding.get("source", "unknown"),
                "sample": finding.get("sample", "")})
            cycle.patch_draft_id = patch.patch_id
            lesson = self.memory.record_outcome(
                f"vaccine immunized {finding.get('type', 'finding')}",
                "SUCCESS", tags=["vaccine", "closed-loop"],
                regression_tested=True)
            cycle.lesson_id = lesson.lesson_id
            cycle.verdict = "IMMUNIZED"
        else:
            cycle.verdict = "BLIND_SPOT"
            self.memory.record_outcome(
                f"vaccine blind spot {finding.get('type', 'finding')}",
                "FAILURE", tags=["vaccine", "blind-spot"],
                regression_tested=False)

        # 5) Anchor the cycle verdict into evidence + vector memory.
        self.evidence.attach_evidence(
            ev.finding_id, "VACCINE-LOOP",
            {"verdict": cycle.verdict,
             "replays": [r.model_dump() for r in cycle.replays]},
            artifact_type="vaccine_cycle",
            summary=f"Vaccine cycle {cycle.cycle_id} -> {cycle.verdict}")
        vector_memory.index_lesson(
            f"vaccine {cycle.verdict.lower()} {finding.get('type','finding')} "
            f"{finding.get('sample','')[:60]}",
            cycle.verdict,
            metadata={"cycle_id": cycle.cycle_id, "tags": ["vaccine"],
                      "failed_round": max_failed if not detected else None})

        cycle.finished_at = time.time()
        cycle.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.cycles[cycle.cycle_id] = cycle
        return cycle

    def get_report(self) -> Dict[str, Any]:
        verdicts: Dict[str, int] = {}
        for c in self.cycles.values():
            verdicts[c.verdict] = verdicts.get(c.verdict, 0) + 1
        return {
            "total_cycles": len(self.cycles),
            "by_verdict": verdicts,
            "immunized": verdicts.get("IMMUNIZED", 0),
            "blind_spots": verdicts.get("BLIND_SPOT", 0),
            "closed_loop_rate": round(
                verdicts.get("IMMUNIZED", 0) / max(1, len(self.cycles)), 3),
            "recent": [c.model_dump() for c in list(self.cycles.values())[-5:]],
        }


# Global Vaccine Engine
vaccine_engine = VaccineEngine()
