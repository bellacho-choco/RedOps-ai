"""
====================================================================
PROJECT REDOPS-OMEGA - CONTINUOUS COGNITION DAEMON (PHASE IV: 2070)
Persistent autonomous cyber reasoning: the daemon continuously monitors
World-Model drift, re-validates standing findings, forecasts the top
counterfactual attack paths, and raises re-assessment directives when
the environment's security state evolves. Blueprint Section 15 Phase IV.
====================================================================
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.cypher_engine import graph_engine
from backend.attack_path_engine import attack_path_engine, counterfactual_simulator
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory
from backend.swarm_bus import swarm_bus


class DriftEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"drift-{uuid.uuid4().hex[:8]}")
    detected_at: float = Field(default_factory=time.time)
    added_nodes: List[str] = Field(default_factory=list)
    removed_nodes: List[str] = Field(default_factory=list)
    added_edges: int = 0
    removed_edges: int = 0
    severity: str = "INFO"             # INFO | ELEVATED | CRITICAL


class CognitionCycleReport(BaseModel):
    cycle: int
    drift: Optional[DriftEvent] = None
    top_forecast: Optional[Dict[str, Any]] = None
    revalidation: Dict[str, Any] = Field(default_factory=dict)
    directive: str = "OBSERVE"         # OBSERVE | REASSESS | ALERT
    elapsed_ms: float = 0.0


class ContinuousCognitionDaemon:
    """
    The 2070 principle made concrete: one-shot pentest -> continuous
    adversarial simulation. Each cycle:

      1. SNAPSHOT  — fingerprint the World Model (nodes + edges)
      2. DRIFT     — diff against the previous fingerprint
      3. FORECAST  — simulate compromise of the top-scored entry point
      4. REVALIDATE — re-check standing VALIDATED findings for staleness
      5. DIRECTIVE — decide whether the swarm must re-assess
    """
    def __init__(self, interval_s: float = 30.0):
        self.interval_s = interval_s
        self.running = False
        self.cycle_count = 0
        self._task: Optional[asyncio.Task] = None
        self._last_fingerprint: Optional[Dict[str, set]] = None
        self.history: List[CognitionCycleReport] = []

    # ----------------------------------------------------------------
    def _fingerprint(self) -> Dict[str, set]:
        return {
            "nodes": set(graph_engine.nodes.keys()),
            "edges": set(graph_engine.edges.keys()),
        }

    def _detect_drift(self, current: Dict[str, set]) -> Optional[DriftEvent]:
        if self._last_fingerprint is None:
            return None
        prev = self._last_fingerprint
        added_n = sorted(current["nodes"] - prev["nodes"])
        removed_n = sorted(prev["nodes"] - current["nodes"])
        added_e = len(current["edges"] - prev["edges"])
        removed_e = len(prev["edges"] - current["edges"])
        if not (added_n or removed_n or added_e or removed_e):
            return None
        severity = "INFO"
        if added_n or removed_n:
            severity = "ELEVATED"
        if any("CrownJewel" in graph_engine.nodes[n].labels for n in added_n
               if n in graph_engine.nodes):
            severity = "CRITICAL"
        return DriftEvent(
            added_nodes=added_n, removed_nodes=removed_n,
            added_edges=added_e, removed_edges=removed_e, severity=severity)

    # ----------------------------------------------------------------
    async def run_cycle(self) -> CognitionCycleReport:
        started = time.perf_counter()
        self.cycle_count += 1
        report = CognitionCycleReport(cycle=self.cycle_count)

        current = self._fingerprint()
        drift = self._detect_drift(current)
        self._last_fingerprint = current
        report.drift = drift

        # Forecast: simulate the most dangerous known entry point.
        paths = attack_path_engine.enumerate_paths()
        if paths:
            top = paths[0]
            sim = counterfactual_simulator.simulate_compromise(top.nodes[0])
            report.top_forecast = {
                "path_id": top.path_id, "score": top.score,
                "terminal_impact": sim.terminal_impact,
                "reachable_crown_jewels": sim.reachable_crown_jewels,
            }

        # Revalidate standing findings (staleness check).
        summary = evidence_engine.get_state_summary()
        report.revalidation = {
            "validated": summary["by_state"].get("VALIDATED", 0),
            "false_positives": summary["by_state"].get("FALSE_POSITIVE", 0),
        }

        # Directive synthesis.
        if drift and drift.severity == "CRITICAL":
            report.directive = "ALERT"
        elif drift or (report.top_forecast or {}).get("terminal_impact", 0) >= 0.7:
            report.directive = "REASSESS"

        report.elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self.history.append(report)

        if report.directive != "OBSERVE":
            from backend.swarm_bus import AgentMessage
            await swarm_bus.publish(AgentMessage(
                message_id=f"cog-{report.cycle}",
                source_agent="COGNITION-DAEMON", target_agent="OVERLORD-PRIME",
                event_type=f"DRIFT_DIRECTIVE:{report.directive}",
                content=f"Cycle {report.cycle}: security state evolved",
                meta={"drift": drift.model_dump() if drift else None,
                      "forecast": report.top_forecast}))
            strategy_memory.push_session_event(
                "COGNITION-DAEMON",
                f"cycle {report.cycle}: directive={report.directive}")
        return report

    # ----------------------------------------------------------------
    async def _loop(self):
        while self.running:
            try:
                await self.run_cycle()
            except Exception:
                pass  # the daemon observes; it never takes the swarm down
            await asyncio.sleep(self.interval_s)

    def start(self):
        if self.running:
            return {"status": "ALREADY_RUNNING", "interval_s": self.interval_s}
        self.running = True
        self._task = asyncio.create_task(self._loop())
        return {"status": "STARTED", "interval_s": self.interval_s}

    def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        return {"status": "STOPPED", "cycles_completed": self.cycle_count}

    def get_state(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "interval_s": self.interval_s,
            "cycles_completed": self.cycle_count,
            "last_directive": self.history[-1].directive if self.history else "NONE",
            "recent_cycles": [r.model_dump() for r in self.history[-5:]],
        }


# Global Cognition Daemon
cognition_daemon = ContinuousCognitionDaemon()
