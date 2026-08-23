"""
REDOPS-OMEGA Phase-I engine integration tests.
Exercises the real engines end-to-end: mission manifests, scope enforcement,
policy gates, tool gateway audit chain, attack-path scoring, counterfactual
simulation, evidence validation and strategy memory.
"""

import asyncio

import pytest

from backend.mission_engine import (
    MissionManifest, TargetScope, RulesOfEngagement, ScopeEnforcer,
    GoalDependencyTree, GoalNode, GoalState, MissionEngine,
)
from backend.policy_engine import (
    PolicyEngine, ActionRequest, PolicyDecision, RiskLevel, CapabilityToken,
)
from backend.tool_gateway import ToolGateway
from backend.cypher_engine import CypherGraphEngine
from backend.evidence_engine import EvidenceEngine, FindingState
from backend.strategy_memory import StrategyMemory
import backend.attack_path_engine as ape


def make_manifest(**kwargs) -> MissionManifest:
    kwargs.setdefault("rules_of_engagement",
                      RulesOfEngagement(max_qps=5, disruptive_actions_allowed=False))
    return MissionManifest(
        name="Test Op",
        target_scope=TargetScope(
            networks=["10.0.0.0/16"],
            domains=["*.lab.internal"],
            exclusions=["10.0.99.0/24", "db-prod.lab.internal"],
        ),
        **kwargs,
    )


# --------------------------------------------------------------------
# Mission & Scope
# --------------------------------------------------------------------
def test_scope_enforcer_networks_and_exclusions():
    enforcer = ScopeEnforcer(make_manifest().target_scope)
    assert enforcer.check("10.0.1.5")["in_scope"]
    assert not enforcer.check("10.0.99.7")["in_scope"]          # excluded CIDR
    assert not enforcer.check("192.168.1.1")["in_scope"]        # outside networks
    assert enforcer.check("web.lab.internal")["in_scope"]       # wildcard domain
    assert not enforcer.check("db-prod.lab.internal")["in_scope"]  # excluded host
    assert not enforcer.check("evil.example.com")["in_scope"]


def test_scope_enforcer_redirect_blocked_after_dns():
    enforcer = ScopeEnforcer(make_manifest().target_scope)
    # Domain is in scope, but it resolves to an out-of-scope IP -> blocked.
    res = enforcer.check("web.lab.internal", resolved_ip="8.8.8.8")
    assert not res["in_scope"]
    assert "redirect" in res["reason"]
    # In-scope resolution passes.
    assert enforcer.check("web.lab.internal", resolved_ip="10.0.2.9")["in_scope"]


def test_goal_tree_dag_and_circuit_breaker():
    tree = GoalDependencyTree()
    tree.add_goal(GoalNode(goal_id="a", title="A", agent="SPECTRE-RECON"))
    tree.add_goal(GoalNode(goal_id="b", title="B", agent="NEXUS-CYPHER", depends_on=["a"]))

    assert [g.goal_id for g in tree.next_ready()] == ["a"]
    tree.mark_running("a")
    tree.mark_done("a", {"ok": True})
    assert [g.goal_id for g in tree.next_ready()] == ["b"]

    # Circuit breaker: 3 failures -> BLOCKED, never rescheduled.
    for _ in range(3):
        tree.mark_running("b")
        tree.mark_failed("b", "boom")
    assert tree.goals["b"].state == GoalState.BLOCKED
    assert tree.is_complete()


def test_goal_tree_rejects_cycles():
    tree = GoalDependencyTree()
    tree.add_goal(GoalNode(goal_id="a", title="A", agent="X"))
    tree.add_goal(GoalNode(goal_id="b", title="B", agent="X"))
    # Introduce a cycle post-hoc and force revalidation.
    tree.goals["a"].depends_on = ["b"]
    tree.goals["b"].depends_on = ["a"]
    with pytest.raises(ValueError, match="cycle"):
        tree._assert_acyclic()


def test_goal_tree_rejects_unknown_dependency():
    tree = GoalDependencyTree()
    with pytest.raises(ValueError, match="unknown goal"):
        tree.add_goal(GoalNode(goal_id="a", title="A", agent="X", depends_on=["ghost"]))


# --------------------------------------------------------------------
# Policy Engine & Capability Tokens
# --------------------------------------------------------------------
def test_policy_role_matrix_and_hazardous_payloads():
    engine = PolicyEngine()
    # SPECTRE-RECON barred from exploit tools -> DENY.
    v = engine.evaluate(ActionRequest(agent="SPECTRE-RECON", tool="exploit_dryrun", target="10.0.0.5"))
    assert v.decision == PolicyDecision.DENY
    # VORTEX-EXPLOIT with a benign probe -> ALLOW.
    v = engine.evaluate(ActionRequest(agent="VORTEX-EXPLOIT", tool="http_probe", target="10.0.0.5"))
    assert v.decision == PolicyDecision.ALLOW
    # Credential dumping params -> CRITICAL risk -> zero-collateral DENY under RoE.
    roe = make_manifest().rules_of_engagement
    v = engine.evaluate(
        ActionRequest(agent="OVERLORD-PRIME", tool="sandbox_exec", target="10.0.0.5",
                      params={"cmd": "mimikatz sekurlsa::logonpasswords"}), roe=roe)
    assert v.decision == PolicyDecision.DENY
    assert v.risk == RiskLevel.CRITICAL
    # High-impact MITRE technique without hazardous text -> approval gate.
    v = engine.evaluate(
        ActionRequest(agent="OVERLORD-PRIME", tool="sandbox_exec", target="10.0.0.5",
                      mitre_techniques=["T1021"]), roe=roe)
    assert v.decision == PolicyDecision.REQUIRE_APPROVAL
    assert v.approval_id
    assert engine.approve(v.approval_id, "tester").status == "APPROVED"
    assert engine.is_approved(v.approval_id)


def test_capability_token_binding():
    issuer = CapabilityToken()
    tok = issuer.issue("SPECTRE-RECON", "port_scan", "m1")
    assert issuer.verify(tok, "SPECTRE-RECON", "port_scan", "m1")
    assert not issuer.verify(tok, "VORTEX-EXPLOIT", "port_scan", "m1")  # wrong agent
    assert not issuer.verify(tok, "SPECTRE-RECON", "exploit_dryrun", "m1")  # wrong tool
    assert not issuer.verify(tok, "SPECTRE-RECON", "port_scan", "m2")   # wrong mission
    assert not issuer.verify(tok + "ff", "SPECTRE-RECON", "port_scan", "m1")  # tampered


# --------------------------------------------------------------------
# Tool Gateway
# --------------------------------------------------------------------
def test_gateway_full_flow_and_audit_chain():
    engine = MissionEngine()
    manifest = make_manifest(
        rules_of_engagement=RulesOfEngagement(max_qps=3, disruptive_actions_allowed=False)
    )
    engine.launch(manifest, "10.0.0.5")

    gateway = ToolGateway()  # fresh ledger, shared global policy engine

    async def fake_probe(target: str, **params):
        return {"target": target, "open": [80]}

    gateway.register_tool("http_probe", fake_probe)

    import backend.tool_gateway as tg
    original = tg.mission_engine
    tg.mission_engine = engine
    try:
        async def run():
            # No token -> denied.
            action = ActionRequest(agent="SPECTRE-RECON", tool="http_probe", target="10.0.0.5")
            r = await gateway.execute(action, capability_token=None)
            assert r["status"] == "DENIED"

            # Out-of-scope target -> denied even with valid token.
            tok = gateway.policy.token_issuer.issue("SPECTRE-RECON", "http_probe", manifest.mission_id)
            r = await gateway.execute(
                ActionRequest(agent="SPECTRE-RECON", tool="http_probe", target="192.168.9.9"),
                capability_token=tok)
            assert r["status"] == "DENIED"
            assert "Scope" in r["reason"]

            # Valid token + in-scope -> executed.
            r = await gateway.execute(
                ActionRequest(agent="SPECTRE-RECON", tool="http_probe", target="10.0.0.5"),
                capability_token=tok)
            assert r["status"] == "EXECUTED"
            assert r["result"]["open"] == [80]

            # QPS ceiling: manifest max_qps=5, several calls already this second.
            outcomes = [await gateway.execute(
                ActionRequest(agent="SPECTRE-RECON", tool="http_probe", target="10.0.0.5"),
                capability_token=tok) for _ in range(4)]
            assert any(o["status"] == "DENIED" and "max_qps" in o["reason"] for o in outcomes)

        asyncio.run(run())
        integrity = gateway.verify_ledger_integrity()
        assert integrity["intact"] and integrity["records"] >= 6
    finally:
        tg.mission_engine = original


def test_gateway_sealed_without_mission():
    import backend.tool_gateway as tg
    gateway = ToolGateway()
    original = tg.mission_engine
    tg.mission_engine = MissionEngine()  # empty: no active mission
    try:
        async def run():
            r = await gateway.execute(
                ActionRequest(agent="OVERLORD-PRIME", tool="http_probe", target="10.0.0.1"),
                capability_token="x")
            assert r["status"] == "DENIED"
            assert "sealed" in r["reason"]
        asyncio.run(run())
    finally:
        tg.mission_engine = original


# --------------------------------------------------------------------
# Attack-Path Engine & Counterfactual Simulator
# --------------------------------------------------------------------
@pytest.fixture
def omega_graph(monkeypatch):
    g = CypherGraphEngine()
    g.nodes.clear(); g.edges.clear(); g.adjacency.clear(); g.rev_adjacency.clear()
    g.add_node("internet", ["EntryPoint"], {"internet_facing": True})
    g.add_node("lb", ["Service"], {})
    g.add_node("webapp", ["Host"], {})
    g.add_node("vuln-sqli", ["Vulnerability"], {"severity": "HIGH"})
    g.add_node("svc-acct", ["Identity"], {})
    g.add_node("vault", ["CrownJewel"], {"sensitive": True})
    g.add_edge("internet", "lb", "ROUTES_TO")
    g.add_edge("lb", "webapp", "FORWARDS_TO")
    g.add_edge("webapp", "vuln-sqli", "HAS_RISK", {"severity": "HIGH"})
    g.add_edge("vuln-sqli", "svc-acct", "ENABLES_ACCESS")
    g.add_edge("svc-acct", "vault", "CAN_READ")
    monkeypatch.setattr(ape, "graph_engine", g)
    return g


def test_attack_path_enumeration_and_scoring(omega_graph):
    engine = ape.AttackPathEngine()
    paths = engine.enumerate_paths()
    assert paths, "expected at least one kill-chain"
    top = paths[0]
    assert top.nodes[0] == "internet"
    assert top.crown_jewel == "vault"
    assert top.score > 0
    # Weakest-link exploitability should reflect the HIGH vuln on the path.
    assert top.score_factors.exploitability == 0.8
    assert top.score_factors.asset_criticality == 10.0


def test_counterfactual_simulation(omega_graph):
    sim = ape.CounterfactualSimulator()
    result = sim.simulate_compromise("webapp")
    assert result.terminal_impact > 0
    assert "vault" in result.reachable_crown_jewels
    assert "IF attacker obtains 'webapp'" in result.hypothesis
    assert any("ENABLES_ACCESS" in s.consequence for s in result.steps)


# --------------------------------------------------------------------
# Evidence & Validation Engine
# --------------------------------------------------------------------
def test_evidence_lifecycle_and_fp_downgrade():
    engine = EvidenceEngine()
    f = engine.register_finding("Missing HSTS", "10.0.0.5", "VORTEX-EXPLOIT", "LOW")
    assert f.state == FindingState.HYPOTHESIS

    engine.attach_evidence(f.finding_id, "VORTEX-EXPLOIT",
                           {"status": 200, "headers": {"server": "nginx"}},
                           artifact_type="http_response")
    engine.attach_evidence(f.finding_id, "VORTEX-EXPLOIT",
                           {"confirm": True}, artifact_type="scan_output")
    f = engine.findings[f.finding_id]
    assert f.state == FindingState.VALIDATED
    assert f.repro_script and "curl" in f.repro_script

    # Token re-verification round-trip.
    tok = f.evidence[0]
    assert engine.verify_token(tok.token_id, {"status": 200, "headers": {"server": "nginx"}})
    assert not engine.verify_token(tok.token_id, {"tampered": True})

    # Contradiction path on a fresh finding.
    f2 = engine.register_finding("Suspected RCE", "10.0.0.6", "VORTEX-EXPLOIT", "HIGH")
    engine.attach_evidence(f2.finding_id, "VORTEX-EXPLOIT", "weak-signal")
    engine.report_contradiction(f2.finding_id, "expected marker absent in response")
    engine.report_contradiction(f2.finding_id, "second probe also negative")
    assert engine.findings[f2.finding_id].state == FindingState.FALSE_POSITIVE
    summary = engine.get_state_summary()
    assert summary["by_state"]["VALIDATED"] == 1
    assert summary["by_state"]["FALSE_POSITIVE"] == 1


# --------------------------------------------------------------------
# Strategy Memory
# --------------------------------------------------------------------
def test_strategy_memory_lessons_and_recall():
    mem = StrategyMemory()
    mem.record_outcome("SYN scan 10.0.0.5:443 tls", "FAILURE", tags=["recon"])
    mem.record_outcome("SYN scan 10.0.0.9:443 tls", "FAILURE", tags=["recon"])  # same signature
    lesson = mem.recall("syn scan 192.168.1.1:8443 tls")
    assert lesson is not None and lesson.occurrences == 2

    mem.record_outcome("header audit on 10.0.0.5", "SUCCESS",
                       tags=["web"], regression_tested=True)
    approved = mem.approved_strategies()
    assert len(approved) == 1 and approved[0]["outcome"] == "SUCCESS"

    mem.set_campaign("compromised_sessions", ["svc-backup"])
    assert mem.get_campaign("compromised_sessions") == ["svc-backup"]
    stats = mem.get_stats()
    assert stats["lessons_total"] == 2
    assert stats["lessons_by_outcome"]["FAILURE"] == 1
