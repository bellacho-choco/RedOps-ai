"""
====================================================================
PROJECT REDOPS-OMEGA - SANDBOX ARCHITECTURE
Disposable Validation Labs: Containerized Dry-Run Tier, Virtualized
AD Rehearsal Tier & Client-Side Payload Tier. Blueprint Section 9.

Every validation is a NON-DESTRUCTIVE dry-run: payloads are analyzed
(statically, entropically, against the World Model) — never executed
against live infrastructure from this engine.
====================================================================
"""

import re
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.defense_engine import defense_engine
from backend.attack_path_engine import counterfactual_simulator
from backend.cypher_engine import graph_engine
from cython_core.fast_entropy import calculate_shannon_entropy


class SandboxTier(str, Enum):
    CONTAINER_LAB = "CONTAINER_LAB"          # exploit syntax/compile dry-runs
    VIRTUALIZED_LAB = "VIRTUALIZED_LAB"      # AD attack-chain rehearsal on World Model
    BROWSER_SANDBOX = "BROWSER_SANDBOX"      # client-side injection static evaluation


class DryRunVerdict(str, Enum):
    SAFE = "SAFE"                      # benign payload, no hazards
    SUSPICIOUS = "SUSPICIOUS"          # evasion markers / entropy anomaly
    MALICIOUS = "MALICIOUS"            # matches attack signatures
    CHAIN_VIABLE = "CHAIN_VIABLE"      # AD rehearsal reached crown jewel
    CHAIN_DEAD_END = "CHAIN_DEAD_END"  # rehearsal path collapsed


class SandboxResult(BaseModel):
    run_id: str = Field(default_factory=lambda: f"sbx-{uuid.uuid4().hex[:8]}")
    tier: SandboxTier
    verdict: DryRunVerdict
    subject: str
    entropy: float = 0.0
    matched_rules: List[str] = Field(default_factory=list)
    chain_narrative: str = ""
    reachable_crown_jewels: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    executed_at: float = Field(default_factory=time.time)
    elapsed_ms: float = 0.0


# Syntax sanity patterns for the container tier (common exploit primitives).
_COMPILE_MARKERS = re.compile(
    r"(import\s+(os|sys|socket|subprocess)|#!/usr/bin/(env\s+)?(python|bash)|"
    r"CREATE\s+(OR\s+REPLACE\s+)?FUNCTION|contract\s+\w+\s*\{|public\s+static\s+void)",
    re.I,
)


class RemoteSandboxNode(BaseModel):
    """A distributed sandbox lab registered under Phase II federation."""
    node_id: str = Field(default_factory=lambda: f"sbx-node-{uuid.uuid4().hex[:6]}")
    endpoint: str                                  # e.g. https://lab-grid-01.internal:9443
    tier: SandboxTier = SandboxTier.CONTAINER_LAB
    capacity: int = 4
    registered_at: float = Field(default_factory=time.time)
    healthy: bool = True


class SandboxManager:
    """
    Coordinates the three disposable lab tiers. All tiers share one rule:
    analyze, never detonate.
    """
    def __init__(self):
        self.history: List[SandboxResult] = []
        self.remote_nodes: Dict[str, RemoteSandboxNode] = {}

    # ---- Phase II: distributed sandbox grid --------------------------
    def register_remote_node(self, endpoint: str,
                             tier: SandboxTier = SandboxTier.CONTAINER_LAB,
                             capacity: int = 4) -> RemoteSandboxNode:
        node = RemoteSandboxNode(endpoint=endpoint, tier=tier, capacity=capacity)
        self.remote_nodes[node.node_id] = node
        return node

    def deregister_remote_node(self, node_id: str) -> bool:
        return self.remote_nodes.pop(node_id, None) is not None

    def grid_status(self) -> Dict[str, Any]:
        return {
            "local_tiers": [t.value for t in SandboxTier],
            "remote_nodes": [n.model_dump() for n in self.remote_nodes.values()],
            "grid_capacity": sum(n.capacity for n in self.remote_nodes.values() if n.healthy),
        }

    # ----------------------------------------------------------------
    # Tier 1: Containerized Linux Lab (exploit dry-run)
    # ----------------------------------------------------------------
    def dry_run_exploit(self, payload: str, name: str = "payload") -> SandboxResult:
        started = time.perf_counter()
        verdict = defense_engine.inspect(payload)
        entropy = verdict.entropy
        notes: List[str] = []

        if _COMPILE_MARKERS.search(payload):
            notes.append("recognized exploit/source syntax markers")
        if entropy > 7.2:
            notes.append("high entropy: packed/encrypted body suspected")
        elif entropy > 5.5:
            notes.append("moderate entropy: possible encoding layer")

        if verdict.matched_rules:
            final = DryRunVerdict.MALICIOUS
        elif verdict.entropy_anomaly:
            final = DryRunVerdict.SUSPICIOUS
        else:
            final = DryRunVerdict.SAFE

        result = SandboxResult(
            tier=SandboxTier.CONTAINER_LAB, verdict=final, subject=name,
            entropy=entropy, matched_rules=verdict.matched_rules, notes=notes,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self.history.append(result)
        return result

    # ----------------------------------------------------------------
    # Tier 2: Virtualized Lab (AD / attack-chain rehearsal)
    # ----------------------------------------------------------------
    def rehearse_attack_chain(self, seed_node: str) -> SandboxResult:
        """
        Rehearse a lateral-movement chain against the in-memory World
        Model clone — the AD-lab equivalent of detonating in a VM snapshot.
        """
        started = time.perf_counter()
        sim = counterfactual_simulator.simulate_compromise(seed_node)
        viable = bool(sim.reachable_crown_jewels)

        notes = []
        if seed_node not in graph_engine.nodes:
            notes.append("seed node absent from World Model; rehearsal inconclusive")

        result = SandboxResult(
            tier=SandboxTier.VIRTUALIZED_LAB,
            verdict=DryRunVerdict.CHAIN_VIABLE if viable else DryRunVerdict.CHAIN_DEAD_END,
            subject=seed_node,
            chain_narrative=sim.narrative,
            reachable_crown_jewels=sim.reachable_crown_jewels,
            notes=notes,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self.history.append(result)
        return result

    # ----------------------------------------------------------------
    # Tier 3: Browser Sandbox (client-side payload static evaluation)
    # ----------------------------------------------------------------
    def evaluate_client_payload(self, html_or_script: str,
                                name: str = "client-payload") -> SandboxResult:
        started = time.perf_counter()
        verdict = defense_engine.inspect(html_or_script)
        notes: List[str] = []

        dom_sinks = re.findall(r"(?i)(innerHTML|document\.write|eval\s*\(|location\.hash|postMessage)", html_or_script)
        if dom_sinks:
            notes.append(f"DOM sinks present: {sorted(set(dom_sinks))}")

        if "SIG-XSS-002" in verdict.matched_rules:
            final = DryRunVerdict.MALICIOUS
        elif verdict.matched_rules or dom_sinks:
            final = DryRunVerdict.SUSPICIOUS
        else:
            final = DryRunVerdict.SAFE

        result = SandboxResult(
            tier=SandboxTier.BROWSER_SANDBOX, verdict=final, subject=name,
            entropy=verdict.entropy, matched_rules=verdict.matched_rules, notes=notes,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self.history.append(result)
        return result

    # ----------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        by_tier: Dict[str, int] = {}
        by_verdict: Dict[str, int] = {}
        for r in self.history:
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            by_verdict[r.verdict.value] = by_verdict.get(r.verdict.value, 0) + 1
        return {
            "total_dry_runs": len(self.history),
            "by_tier": by_tier,
            "by_verdict": by_verdict,
        }


# Global Sandbox Manager
sandbox_manager = SandboxManager()
