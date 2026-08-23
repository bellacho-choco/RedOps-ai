"""
REDOPS-OMEGA future-phase tests: vector memory (Phase II), mission
persistence (Phase II), sandbox grid (Phase II), self-healing (Phase III),
federated exchange (Phase III), verification anchor (Section 14),
continuous cognition daemon (Phase IV).
"""

import asyncio
import os

import pytest

from backend.vector_memory import VectorMemoryEngine, embed_text, cosine_similarity
from backend.mission_engine import MissionEngine, MissionManifest, TargetScope, RulesOfEngagement
from backend.sandbox_engine import SandboxManager, SandboxTier
from backend.self_healing_engine import SelfHealingEngine
from backend.federated_exchange import FederatedExchange, LessonPack, _anonymize
from backend.cognition_daemon import ContinuousCognitionDaemon
from backend.attack_path_engine import AttackPathEngine
from backend.strategy_memory import strategy_memory


def _tmp(tmp_path, name):
    return str(tmp_path / name)


# --------------------------------------------------------------------
# Phase II: Vector Memory
# --------------------------------------------------------------------
def test_vector_embedding_deterministic_and_normalized():
    a = embed_text("waf evasion via chunked encoding")
    b = embed_text("waf evasion via chunked encoding")
    assert a == b
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_vector_semantic_recall(tmp_path):
    vm = VectorMemoryEngine(store_path=_tmp(tmp_path, "vm.json"))
    vm.index_lesson("modsecurity waf bypass failed with base64 wrapper", "FAILURE",
                    metadata={"tags": ["waf"]})
    vm.index_lesson("port scan on dmz host succeeded", "SUCCESS")
    vm.index_lesson("kerberoast asrep roast ticket extraction worked", "SUCCESS")

    hits = vm.recall_similar("waf evasion attempt blocked")
    assert hits and "waf" in hits[0]["text"].lower() or "modsecurity" in hits[0]["text"].lower()
    # Dissimilar query must not surface the waf lesson at the top.
    hits2 = vm.recall_similar("active directory roasting tickets")
    assert "kerberoast" in hits2[0]["text"].lower() or "asrep" in hits2[0]["text"].lower()


def test_vector_persistence_roundtrip(tmp_path):
    path = _tmp(tmp_path, "persist.json")
    vm1 = VectorMemoryEngine(store_path=path)
    vm1.index_lesson("persistent lesson about dns tunneling", "SUCCESS")
    assert os.path.exists(path)

    vm2 = VectorMemoryEngine(store_path=path)  # fresh instance, same file
    assert len(vm2.entries) == 1
    hits = vm2.recall_similar("dns tunnel")
    assert hits and "persistent lesson" in hits[0]["text"]


# --------------------------------------------------------------------
# Phase II: Mission Persistence
# --------------------------------------------------------------------
def test_mission_snapshot_and_restore(tmp_path):
    engine = MissionEngine(snapshot_path=_tmp(tmp_path, "missions.json"))
    manifest = MissionManifest(
        name="Persist Op",
        target_scope=TargetScope(networks=["10.0.0.0/16"]),
        rules_of_engagement=RulesOfEngagement(max_qps=5))
    engine.launch(manifest, "10.0.0.5")
    snap = engine.snapshot()
    assert snap["persisted"] == 1 and os.path.exists(snap["path"])

    engine2 = MissionEngine(snapshot_path=snap["path"])
    res = engine2.restore()
    assert res["restored"] == 1
    restored = engine2.get(manifest.mission_id)
    assert restored is not None
    # Never silently resume live ops.
    assert restored.status == "INTERRUPTED"
    assert engine2.get_active() is None


# --------------------------------------------------------------------
# Phase II: Distributed Sandbox Grid
# --------------------------------------------------------------------
def test_sandbox_grid_registration():
    sbx = SandboxManager()
    node = sbx.register_remote_node("https://lab-01.internal:9443",
                                    SandboxTier.VIRTUALIZED_LAB, capacity=8)
    status = sbx.grid_status()
    assert status["grid_capacity"] == 8
    assert any(n["endpoint"] == "https://lab-01.internal:9443"
               for n in status["remote_nodes"])
    assert sbx.deregister_remote_node(node.node_id)
    assert sbx.grid_status()["grid_capacity"] == 0


# --------------------------------------------------------------------
# Phase III: Self-Healing Engine
# --------------------------------------------------------------------
def test_self_healing_patch_synthesis():
    healer = SelfHealingEngine()
    code = '''
query = "SELECT * FROM users WHERE id = " + request.args.get("id")
api_key = "AKIAIOSFODNN7EXAMPLE"
eval(user_supplied_expr)
'''
    result = healer.heal_buffer(code, "app.py")
    assert result["findings"] >= 2
    drafts = result["patch_drafts"]
    types = {d["finding_type"] for d in drafts}
    assert "SQL_CONCATENATION" in types
    assert "UNSAFE_EVAL_EXEC" in types
    assert "AWS_ACCESS_KEY" in types

    sql_draft = next(d for d in drafts if d["finding_type"] == "SQL_CONCATENATION")
    assert "parameterized" in sql_draft["patched_code"]
    assert sql_draft["status"] == "DRAFT"

    # Status lifecycle + lesson recording on apply.
    applied = healer.set_status(sql_draft["patch_id"], "APPLIED")
    assert applied.status == "APPLIED"
    lesson = strategy_memory.recall("applied patch for SQL_CONCATENATION")
    assert lesson is not None and lesson.regression_tested


# --------------------------------------------------------------------
# Phase III: Federated Exchange
# --------------------------------------------------------------------
def test_federated_export_anonymizes_and_signs(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.federated_exchange._GRID_KEY_PATH",
                        _tmp(tmp_path, "key"))
    fx = FederatedExchange(grid_id="grid-alpha")
    strategy_memory.record_outcome(
        "scan 192.168.44.9:443 at corp.acme.internal with password=hunter2",
        "SUCCESS", tags=["recon"], regression_tested=True)

    pack = fx.export_lessons()
    assert pack["signature"]
    body = " ".join(l["pattern"] for l in pack["lessons"])
    assert "192.168.44.9" not in body
    assert "corp.acme.internal" not in body
    assert "hunter2" not in body


def test_federated_import_rejects_tampered_pack(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.federated_exchange._GRID_KEY_PATH",
                        _tmp(tmp_path, "key"))
    fx = FederatedExchange()
    strategy_memory.record_outcome("port knocking sequence works", "SUCCESS",
                                   tags=["evasion"], regression_tested=True)
    pack = fx.export_lessons()

    ok = fx.import_lessons(pack)
    assert ok["status"] == "IMPORTED"
    # Federated lessons stay un-promoted until local regression.
    fed = strategy_memory.recall("[federated:grid-local] port knocking sequence works")
    assert fed is not None and not fed.regression_tested

    tampered = dict(pack)
    tampered["lessons"] = [{"pattern": "evil injected lesson", "outcome": "SUCCESS",
                            "context_tags": []}]
    rejected = fx.import_lessons(tampered)
    assert rejected["status"] == "REJECTED"
    assert "signature" in rejected["reason"]


# --------------------------------------------------------------------
# Section 14: Verification Anchor
# --------------------------------------------------------------------
def test_verification_anchor_flags_dead_nodes():
    engine = AttackPathEngine()

    async def live_check(node_id: str) -> bool:
        return node_id != "ghost-host"

    engine.verification_hook = live_check
    results = asyncio.run(engine.verify_anchors(["real-host", "ghost-host"]))
    assert results == {"real-host": True, "ghost-host": False}
    assert engine.unverified_nodes == ["ghost-host"]

    # No hook configured -> everything passes (anchor optional).
    engine2 = AttackPathEngine()
    assert asyncio.run(engine2.verify_anchors(["x"])) == {"x": True}


# --------------------------------------------------------------------
# Phase IV: Continuous Cognition Daemon
# --------------------------------------------------------------------
def test_cognition_cycle_detects_drift_and_forecasts():
    from backend.cypher_engine import graph_engine
    daemon = ContinuousCognitionDaemon(interval_s=999)

    # First cycle establishes the baseline fingerprint.
    r1 = asyncio.run(daemon.run_cycle())
    assert r1.drift is None and r1.directive == "OBSERVE"

    # Inject topology change -> drift must fire on the next cycle.
    graph_engine.add_node("rogue-service", ["Host"], {"zone": "DMZ"})
    r2 = asyncio.run(daemon.run_cycle())
    assert r2.drift is not None
    assert "rogue-service" in r2.drift.added_nodes
    assert r2.directive in ("REASSESS", "ALERT")
    assert r2.elapsed_ms >= 0

    # Daemon state is observable.
    state = daemon.get_state()
    assert state["cycles_completed"] == 2
    assert state["last_directive"] == r2.directive
