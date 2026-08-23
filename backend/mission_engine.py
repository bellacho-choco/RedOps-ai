"""
====================================================================
PROJECT REDOPS-OMEGA - MISSION & GOAL SYSTEM
Mission Manifests, Goal Dependency Trees (DAG) & Circuit Breakers
Blueprint Section 2: policy-bounded mission decomposition.
====================================================================
"""

import ipaddress
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Set

from pydantic import BaseModel, Field


# ====================================================================
# MISSION MANIFEST
# ====================================================================
class TargetScope(BaseModel):
    networks: List[str] = Field(default_factory=list)      # CIDRs, e.g. ["10.0.0.0/16"]
    domains: List[str] = Field(default_factory=list)       # e.g. ["*.example.internal"]
    exclusions: List[str] = Field(default_factory=list)    # CIDRs or hostnames


class RulesOfEngagement(BaseModel):
    max_qps: int = 10
    allowed_hours_utc: Optional[str] = None                # "08:00-22:00" or None = always
    zero_collateral_policy: bool = True
    disruptive_actions_allowed: bool = False
    automatic_exploitation_limit: str = "none"             # none | low-risk | medium-risk


class MissionManifest(BaseModel):
    mission_id: str = Field(default_factory=lambda: f"ops-{uuid.uuid4().hex[:8]}")
    name: str = "Unnamed Operation"
    target_scope: TargetScope = Field(default_factory=TargetScope)
    rules_of_engagement: RulesOfEngagement = Field(default_factory=RulesOfEngagement)
    compliance_frameworks: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class ScopeEnforcer:
    """
    Verifies that a target (IP, CIDR, or domain) lies inside the active
    Mission Manifest. Checked AFTER DNS resolution by the Tool Gateway.
    """
    def __init__(self, scope: TargetScope):
        self.scope = scope
        self._nets = self._parse_networks(scope.networks)
        self._excl_nets = self._parse_networks(
            [e for e in scope.exclusions if self._looks_like_network(e)]
        )
        self._excl_hosts = {
            e.lower() for e in scope.exclusions if not self._looks_like_network(e)
        }

    @staticmethod
    def _looks_like_network(value: str) -> bool:
        try:
            ipaddress.ip_network(value.split("/")[0] if "/" in value else value, strict=False)
            return True
        except ValueError:
            return False

    @staticmethod
    def _parse_networks(values: List[str]) -> List[ipaddress._BaseNetwork]:
        nets = []
        for v in values:
            try:
                nets.append(ipaddress.ip_network(v, strict=False))
            except ValueError:
                continue
        return nets

    def is_excluded_ip(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in n for n in self._excl_nets)

    def is_excluded_host(self, hostname: str) -> bool:
        h = hostname.lower()
        return h in self._excl_hosts

    def _domain_in_scope(self, hostname: str) -> bool:
        h = hostname.lower()
        for pattern in self.scope.domains:
            p = pattern.lower()
            if p.startswith("*."):
                if h.endswith(p[1:]) or h == p[2:]:
                    return True
            elif h == p:
                return True
        return False

    def check(self, target: str, resolved_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns {"in_scope": bool, "reason": str}.
        `resolved_ip` must be provided by the gateway post-DNS-resolution so
        redirects/CNAMEs cannot smuggle out-of-scope traffic.
        """
        host = target.split("//")[-1].split("/")[0].split(":")[0]

        if self.is_excluded_host(host):
            return {"in_scope": False, "reason": f"Host '{host}' is explicitly excluded by manifest"}
        if resolved_ip and self.is_excluded_ip(resolved_ip):
            return {"in_scope": False, "reason": f"Resolved IP {resolved_ip} is explicitly excluded"}

        # IP literal targets
        try:
            addr = ipaddress.ip_address(host)
            if any(addr in n for n in self._excl_nets):
                return {"in_scope": False, "reason": f"IP {host} is explicitly excluded by manifest"}
            in_net = any(addr in n for n in self._nets)
            if in_net:
                return {"in_scope": True, "reason": "IP inside declared networks"}
            if not self._nets and not self.scope.domains:
                return {"in_scope": False, "reason": "Manifest declares no scope"}
            return {"in_scope": False, "reason": f"IP {host} outside declared networks"}
        except ValueError:
            pass

        # Domain targets — also verify the resolved IP when available
        if self._domain_in_scope(host):
            if resolved_ip:
                try:
                    addr = ipaddress.ip_address(resolved_ip)
                    if self._nets and not any(addr in n for n in self._nets):
                        return {
                            "in_scope": False,
                            "reason": f"Domain '{host}' resolves to {resolved_ip} outside declared networks (redirect blocked)"
                        }
                except ValueError:
                    pass
            return {"in_scope": True, "reason": "Domain inside declared scope"}

        return {"in_scope": False, "reason": f"Target '{host}' not covered by manifest scope"}


# ====================================================================
# GOAL DEPENDENCY TREE (DAG)
# ====================================================================
class GoalState(str, Enum):
    PENDING = "PENDING"        # waiting on prerequisites
    READY = "READY"            # prerequisites met, schedulable
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"        # circuit-breaker tripped


class GoalNode(BaseModel):
    goal_id: str
    title: str
    agent: str                          # hero responsible
    depends_on: List[str] = Field(default_factory=list)
    state: GoalState = GoalState.PENDING
    attempts: int = 0
    max_attempts: int = 3               # circuit-breaker threshold
    result: Optional[Dict[str, Any]] = None
    created_at: float = Field(default_factory=time.time)


class GoalDependencyTree:
    """
    DAG of mission goals with state propagation and a circuit breaker:
    after `max_attempts` failures a goal is BLOCKED and dependents stay
    PENDING forever, preventing endless exploit-retry loop locks.
    """
    def __init__(self):
        self.goals: Dict[str, GoalNode] = {}

    def add_goal(self, goal: GoalNode):
        if goal.goal_id in self.goals:
            raise ValueError(f"Duplicate goal_id '{goal.goal_id}'")
        self.goals[goal.goal_id] = goal
        self._assert_acyclic()
        self._refresh_ready()

    def _assert_acyclic(self):
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {g: WHITE for g in self.goals}

        def visit(node: str):
            color[node] = GRAY
            for dep in self.goals[node].depends_on:
                if dep not in self.goals:
                    raise ValueError(f"Goal '{node}' depends on unknown goal '{dep}'")
                if color[dep] == GRAY:
                    raise ValueError(f"Dependency cycle detected at goal '{dep}'")
                if color[dep] == WHITE:
                    visit(dep)
            color[node] = BLACK

        for g in self.goals:
            if color[g] == WHITE:
                visit(g)

    def _refresh_ready(self):
        for goal in self.goals.values():
            if goal.state != GoalState.PENDING:
                continue
            deps = [self.goals[d] for d in goal.depends_on]
            if all(d.state == GoalState.DONE for d in deps):
                goal.state = GoalState.READY

    def next_ready(self) -> List[GoalNode]:
        return [g for g in self.goals.values() if g.state == GoalState.READY]

    def mark_running(self, goal_id: str):
        g = self.goals[goal_id]
        if g.state != GoalState.READY:
            raise ValueError(f"Goal '{goal_id}' is not READY (state={g.state})")
        g.state = GoalState.RUNNING
        g.attempts += 1

    def mark_done(self, goal_id: str, result: Optional[Dict[str, Any]] = None):
        g = self.goals[goal_id]
        g.state = GoalState.DONE
        g.result = result
        self._refresh_ready()

    def mark_failed(self, goal_id: str, error: Optional[str] = None):
        g = self.goals[goal_id]
        if g.attempts >= g.max_attempts:
            g.state = GoalState.BLOCKED
            g.result = {"error": error, "circuit_breaker": "TRIPPED"}
        else:
            g.state = GoalState.READY
            g.result = {"error": error}

    def is_complete(self) -> bool:
        return all(g.state in (GoalState.DONE, GoalState.BLOCKED) for g in self.goals.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_goals": len(self.goals),
            "states": {s.value: sum(1 for g in self.goals.values() if g.state == s) for s in GoalState},
            "goals": [g.model_dump() for g in self.goals.values()],
        }


# ====================================================================
# MISSION ENGINE
# ====================================================================
class Mission:
    def __init__(self, manifest: MissionManifest):
        self.manifest = manifest
        self.scope_enforcer = ScopeEnforcer(manifest.target_scope)
        self.gdt = GoalDependencyTree()
        self.status = "ACTIVE"
        self.created_at = time.time()

    def build_default_gdt(self, target: str) -> GoalDependencyTree:
        """Standard Phase-I kill-chain decomposition for OVERLORD-PRIME."""
        goals = [
            GoalNode(goal_id="g1-recon", title=f"Surface discovery on {target}",
                     agent="SPECTRE-RECON"),
            GoalNode(goal_id="g2-topology", title="Ingest scan into World Model graph",
                     agent="NEXUS-CYPHER", depends_on=["g1-recon"]),
            GoalNode(goal_id="g3-vuln", title="Vulnerability & posture audit",
                     agent="VORTEX-EXPLOIT", depends_on=["g2-topology"]),
            GoalNode(goal_id="g4-paths", title="Attack-path scoring & counterfactual simulation",
                     agent="NEXUS-CYPHER", depends_on=["g3-vuln"]),
            GoalNode(goal_id="g5-entropy", title="Entropy & secret sweep",
                     agent="CIPHER-MORPH", depends_on=["g3-vuln"]),
            GoalNode(goal_id="g6-evidence", title="Evidence validation & FP analysis",
                     agent="CHRONO-DEBRIEF", depends_on=["g4-paths", "g5-entropy"]),
            GoalNode(goal_id="g7-debrief", title="Executive debrief & remediation plan",
                     agent="CHRONO-DEBRIEF", depends_on=["g6-evidence"]),
        ]
        for g in goals:
            self.gdt.add_goal(g)
        return self.gdt


class MissionEngine:
    def __init__(self):
        self.missions: Dict[str, Mission] = {}
        self.active_mission_id: Optional[str] = None

    def launch(self, manifest: MissionManifest, target: str) -> Mission:
        mission = Mission(manifest)
        mission.build_default_gdt(target)
        self.missions[manifest.mission_id] = mission
        self.active_mission_id = manifest.mission_id
        return mission

    def get_active(self) -> Optional[Mission]:
        if self.active_mission_id:
            return self.missions.get(self.active_mission_id)
        return None

    def get(self, mission_id: str) -> Optional[Mission]:
        return self.missions.get(mission_id)

    def abort(self, mission_id: str) -> bool:
        m = self.missions.get(mission_id)
        if not m:
            return False
        m.status = "ABORTED"
        if self.active_mission_id == mission_id:
            self.active_mission_id = None
        return True


# Global Mission Engine
mission_engine = MissionEngine()
