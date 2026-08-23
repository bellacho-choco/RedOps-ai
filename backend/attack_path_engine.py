"""
====================================================================
PROJECT REDOPS-OMEGA - ATTACK-PATH ENGINE & COUNTERFACTUAL SIMULATOR
Kill-chain enumeration over the World Model, Path Scoring Model &
IF->THEN what-if compromise propagation. Blueprint Section 8.
====================================================================
"""

import time
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.cypher_engine import graph_engine


class PathScore(BaseModel):
    likelihood: float = 0.5        # 0.0 - 1.0
    exploitability: float = 0.5    # 0.1 - 1.0
    privilege_gain: float = 1.0    # 1.0 - 10.0
    asset_criticality: float = 1.0 # 1.0 - 10.0
    blast_radius: float = 1.0      # 1.0 - 5.0

    @property
    def total(self) -> float:
        return round(
            self.likelihood * self.exploitability *
            self.privilege_gain * self.asset_criticality * self.blast_radius, 3
        )


class AttackPath(BaseModel):
    path_id: str
    nodes: List[str]
    hops: int
    score: float
    score_factors: PathScore
    crown_jewel: str
    generated_at: float = Field(default_factory=time.time)


# Severity -> exploitability heuristic; a validated risk is easier to weaponize.
SEVERITY_EXPLOITABILITY = {"CRITICAL": 0.95, "HIGH": 0.8, "MEDIUM": 0.55, "LOW": 0.3, "INFO": 0.1}

# Node label -> asset criticality heuristic.
def _criticality(node: Dict[str, Any]) -> float:
    labels = set(node.get("labels", []))
    props = node.get("properties", {})
    if "CrownJewel" in labels or props.get("zone") == "CORE_MATRIX":
        return 10.0
    if "Vulnerability" in labels or "SecurityRisk" in labels:
        sev = props.get("severity", "MEDIUM")
        return {"CRITICAL": 8.0, "HIGH": 6.5, "MEDIUM": 4.0, "LOW": 2.0}.get(sev, 4.0)
    if "Service" in labels:
        return 3.0
    if "Host" in labels:
        return 5.0
    return 2.0


class AttackPathEngine:
    """
    Enumerates kill-chains from entry points to crown jewels across the
    in-memory World Model and scores each with the Path Scoring Model.
    """
    def __init__(self, max_depth: int = 8, max_paths: int = 64):
        self.max_depth = max_depth
        self.max_paths = max_paths
        # Section 14 Verification Anchor: an optional async hook that
        # live-checks a node's active state before it may be scored into
        # a kill-chain. Protects against cognitive drift / hallucinated
        # topology being treated as ground truth.
        self.verification_hook = None  # async (node_id) -> bool
        self.unverified_nodes: List[str] = []

    async def verify_anchors(self, node_ids: List[str]) -> Dict[str, bool]:
        """Run the verification anchor over path nodes (live check)."""
        results: Dict[str, bool] = {}
        if not self.verification_hook:
            return {nid: True for nid in node_ids}
        for nid in node_ids:
            try:
                results[nid] = bool(await self.verification_hook(nid))
            except Exception:
                results[nid] = False
        self.unverified_nodes = [nid for nid, ok in results.items() if not ok]
        return results

    # ----------------------------------------------------------------
    # Path enumeration (DFS, depth-capped)
    # ----------------------------------------------------------------
    def _entry_points(self) -> List[str]:
        entries = []
        for nid, node in graph_engine.nodes.items():
            labels = node.labels
            props = node.properties
            if ("EntryPoint" in labels or props.get("zone") == "DMZ"
                    or props.get("internet_facing") is True):
                entries.append(nid)
        if not entries:  # fall back: any scanned host is a candidate origin
            entries = [nid for nid, n in graph_engine.nodes.items() if "Host" in n.labels]
        return entries

    def _crown_jewels(self) -> List[str]:
        jewels = []
        for nid, node in graph_engine.nodes.items():
            labels = node.labels
            props = node.properties
            if ("CrownJewel" in labels or props.get("zone") == "CORE_MATRIX"
                    or props.get("sensitive") is True):
                jewels.append(nid)
        if not jewels:  # fall back: highest-severity vulnerabilities
            vulns = [(nid, n) for nid, n in graph_engine.nodes.items()
                     if "Vulnerability" in n.labels or "SecurityRisk" in n.labels]
            order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            vulns.sort(key=lambda kv: order.get(kv[1].properties.get("severity", "LOW"), 0),
                       reverse=True)
            jewels = [nid for nid, _ in vulns[:3]]
        return jewels

    def enumerate_paths(self) -> List[AttackPath]:
        entries, jewels = self._entry_points(), set(self._crown_jewels())
        paths: List[AttackPath] = []

        def dfs(current: str, target: str, trail: List[str], visited: set):
            if len(paths) >= self.max_paths or len(trail) > self.max_depth:
                return
            if current == target:
                paths.append(self._score_path(trail, target))
                return
            for edge_id in graph_engine.adjacency.get(current, []):
                nxt = graph_engine.edges[edge_id].target_id
                if nxt in visited:
                    continue
                visited.add(nxt)
                dfs(nxt, target, trail + [nxt], visited)
                visited.discard(nxt)

        for entry in entries:
            for jewel in jewels:
                if entry == jewel:
                    continue
                dfs(entry, jewel, [entry], {entry})

        paths.sort(key=lambda p: p.score, reverse=True)
        return paths

    def _score_path(self, node_ids: List[str], jewel: str) -> AttackPath:
        nodes = [graph_engine.nodes[nid].to_dict() for nid in node_ids]

        # Exploitability: weakest link dominates (attacker needs every hop).
        exploitability = 1.0
        vuln_hops = 0
        for n in nodes:
            labels = set(n.get("labels", []))
            if "Vulnerability" in labels or "SecurityRisk" in labels:
                vuln_hops += 1
                sev = n.get("properties", {}).get("severity", "MEDIUM")
                exploitability = min(exploitability, SEVERITY_EXPLOITABILITY.get(sev, 0.5))
        if vuln_hops == 0:
            exploitability = 0.2  # no known weakness on path: hypothetical only

        # Likelihood decays with path length; validated findings boost it.
        likelihood = max(0.1, 1.0 - 0.12 * (len(node_ids) - 1))
        if vuln_hops:
            likelihood = min(1.0, likelihood + 0.15)

        # Privilege gain grows with the criticality delta along the chain.
        crits = [_criticality(n) for n in nodes]
        privilege_gain = max(1.0, min(10.0, max(crits) - min(crits) + 1.0))

        # Blast radius: normalized out-degree of the final hop.
        final_degree = len(graph_engine.adjacency.get(node_ids[-1], []))
        blast_radius = max(1.0, min(5.0, 1.0 + final_degree / 2.0))

        factors = PathScore(
            likelihood=round(likelihood, 3),
            exploitability=round(exploitability, 3),
            privilege_gain=round(privilege_gain, 3),
            asset_criticality=round(_criticality(nodes[-1]), 3),
            blast_radius=round(blast_radius, 3),
        )
        return AttackPath(
            path_id=f"path-{hash(tuple(node_ids)) & 0xFFFFFFFF:08x}",
            nodes=node_ids, hops=len(node_ids) - 1,
            score=factors.total, score_factors=factors, crown_jewel=jewel,
        )


# ====================================================================
# COUNTERFACTUAL ATTACK SIMULATOR
# ====================================================================
class SimulationStep(BaseModel):
    condition: str          # IF ...
    consequence: str        # THEN ...
    reached_node: str
    impact_delta: float


class CounterfactualResult(BaseModel):
    seed_node: str
    hypothesis: str
    steps: List[SimulationStep]
    terminal_impact: float
    reachable_crown_jewels: List[str]
    narrative: str


class CounterfactualSimulator:
    """
    What-if dry-runs against the World Model:
    'IF attacker obtains X, THEN Y becomes reachable...' propagated over
    graph edges without touching any live target.
    """
    def __init__(self, max_depth: int = 6):
        self.max_depth = max_depth

    def simulate_compromise(self, seed_node: str) -> CounterfactualResult:
        if seed_node not in graph_engine.nodes:
            return CounterfactualResult(
                seed_node=seed_node,
                hypothesis=f"Node '{seed_node}' not present in World Model",
                steps=[], terminal_impact=0.0, reachable_crown_jewels=[],
                narrative="Simulation aborted: unknown seed node.",
            )

        steps: List[SimulationStep] = []
        visited = {seed_node}
        frontier = [seed_node]
        crown_hits: List[str] = []
        impact = _criticality(graph_engine.nodes[seed_node].to_dict())

        for _ in range(self.max_depth):
            next_frontier = []
            for current in frontier:
                for edge_id in graph_engine.adjacency.get(current, []):
                    edge = graph_engine.edges[edge_id]
                    nxt = edge.target_id
                    if nxt in visited:
                        continue
                    visited.add(nxt)
                    node = graph_engine.nodes[nxt]
                    node_crit = _criticality(node.to_dict())
                    steps.append(SimulationStep(
                        condition=f"attacker controls {current}",
                        consequence=f"{edge.rel_type} grants access to {nxt}",
                        reached_node=nxt,
                        impact_delta=round(node_crit / 10.0, 3),
                    ))
                    impact += node_crit / 10.0
                    if ("CrownJewel" in node.labels or node.properties.get("sensitive") is True
                            or node.properties.get("zone") == "CORE_MATRIX"):
                        crown_hits.append(nxt)
                    next_frontier.append(nxt)
            frontier = next_frontier
            if not frontier:
                break

        narrative_lines = []
        for i, s in enumerate(steps):
            prefix = "IF" if i == 0 else "    THEN IF"
            narrative_lines.append(f"{prefix} {s.condition}\n    THEN {s.consequence}")
        if crown_hits:
            narrative_lines.append(f"    THEN crown jewel(s) exposed: {', '.join(crown_hits)}")

        return CounterfactualResult(
            seed_node=seed_node,
            hypothesis=f"IF attacker obtains '{seed_node}'",
            steps=steps,
            terminal_impact=round(impact, 3),
            reachable_crown_jewels=crown_hits,
            narrative="\n".join(narrative_lines) or "No propagation possible from seed node.",
        )


# Global instances
attack_path_engine = AttackPathEngine()
counterfactual_simulator = CounterfactualSimulator()
