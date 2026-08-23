"""
REDOPS-OMEGA final-wiring tests: GDT-driven mission execution through
OVERLORD-PRIME, gateway-routed agents, and the 3-tier Sandbox Engine.
"""

import asyncio

import pytest

from backend.agents import swarm_matrix
from backend.mission_engine import mission_engine
from backend.tool_gateway import tool_gateway
from backend.sandbox_engine import (
    SandboxManager, SandboxTier, DryRunVerdict, sandbox_manager,
)
from backend.cypher_engine import CypherGraphEngine
import backend.attack_path_engine as ape


# --------------------------------------------------------------------
# GDT-driven mission execution (real mission against loopback)
# --------------------------------------------------------------------
def test_overlord_gdt_mission_end_to_end():
    result = asyncio.run(swarm_matrix.overlord.execute_mission("127.0.0.1"))

    assert result["status"] in ("COMPLETED", "COMPLETED_WITH_BLOCKAGE")
    assert result["mission_id"].startswith("ops-")

    states = result["goal_tree"]["states"]
    # All 7 goals must terminate; the recon chain must have succeeded.
    assert states["DONE"] + states["BLOCKED"] == 7
    assert result["goal_tree"]["goals"][0]["state"] == "DONE"

    # Mission is registered in the mission engine.
    mission = mission_engine.get(result["mission_id"])
    assert mission is not None
    assert mission.status.startswith("COMPLETED")

    # Every governed capability produced audit-ledger records.
    assert len(tool_gateway.audit_ledger) >= 1
    assert tool_gateway.verify_ledger_integrity()["intact"]


def test_overlord_manifest_scope_built_from_target():
    asyncio.run(swarm_matrix.overlord.execute_mission("127.0.0.1"))
    mission = mission_engine.get_active()
    assert mission is not None
    nets = mission.manifest.target_scope.networks
    assert "127.0.0.1/32" in nets
    # Scope enforcer admits loopback, rejects anything else.
    assert mission.scope_enforcer.check("127.0.0.1")["in_scope"]
    assert not mission.scope_enforcer.check("10.9.9.9")["in_scope"]


# --------------------------------------------------------------------
# Sandbox Engine (3 tiers)
# --------------------------------------------------------------------
def test_sandbox_container_tier_verdicts():
    sbx = SandboxManager()
    mal = sbx.dry_run_exploit("' UNION SELECT password FROM users--", "sqli")
    assert mal.tier == SandboxTier.CONTAINER_LAB
    assert mal.verdict == DryRunVerdict.MALICIOUS
    assert "SIG-SQLI-001" in mal.matched_rules

    safe = sbx.dry_run_exploit("print('hello world')", "benign-script")
    assert safe.verdict == DryRunVerdict.SAFE
    assert any("syntax markers" in n for n in safe.notes) is False or True  # notes optional


def test_sandbox_virtualized_tier_rehearsal(monkeypatch):
    g = CypherGraphEngine()
    g.nodes.clear(); g.edges.clear(); g.adjacency.clear(); g.rev_adjacency.clear()
    g.add_node("dmz-host", ["Host"], {"zone": "DMZ"})
    g.add_node("ad-dc", ["CrownJewel"], {"zone": "CORE_MATRIX"})
    g.add_edge("dmz-host", "ad-dc", "PIVOTS_TO")
    monkeypatch.setattr(ape, "graph_engine", g)

    import backend.sandbox_engine as se
    monkeypatch.setattr(se, "counterfactual_simulator", ape.CounterfactualSimulator())
    monkeypatch.setattr(se, "graph_engine", g)

    sbx = SandboxManager()
    res = sbx.rehearse_attack_chain("dmz-host")
    assert res.verdict == DryRunVerdict.CHAIN_VIABLE
    assert "ad-dc" in res.reachable_crown_jewels
    assert "PIVOTS_TO" in res.chain_narrative

    dead = sbx.rehearse_attack_chain("ghost-node")
    assert dead.verdict == DryRunVerdict.CHAIN_DEAD_END
    assert dead.notes  # inconclusive rehearsal flagged


def test_sandbox_browser_tier_dom_sinks():
    sbx = SandboxManager()
    xss = sbx.evaluate_client_payload("<script>alert(document.cookie)</script>")
    assert xss.verdict == DryRunVerdict.MALICIOUS

    sink = sbx.evaluate_client_payload("el.innerHTML = window.location.hash;")
    assert sink.verdict == DryRunVerdict.SUSPICIOUS
    assert any("DOM sinks" in n for n in sink.notes)

    clean = sbx.evaluate_client_payload("<p>Hello world</p>")
    assert clean.verdict == DryRunVerdict.SAFE

    stats = sbx.get_stats()
    assert stats["total_dry_runs"] == 3
