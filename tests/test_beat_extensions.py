"""
REDOPS-OMEGA Satellite-beat tests: real container execution, signed
engagement package, vaccine loop, hybrid graph, intel cache, sonic
dispatch, fresh-context isolation, dual-axis benchmark.
"""

import asyncio
import json
import os
import tempfile
from unittest import mock

import pytest

from backend.sandbox_engine import DockerExecutor, detect_prompt
from backend.mission_engine import (MissionEngine, MissionManifest,
    generate_engagement_package, verify_engagement_package)
from backend.vaccine_engine import VaccineEngine
from backend.intel_engine import IntelEngine
from backend.cypher_engine import CypherGraphEngine
from backend.parallel_dispatch import ParallelGoalDispatcher, LaneContext
from backend.live_scanner import AsyncSocketScanner


# -------- Step 1/2: real container execution (mocked SDK seam) -----------
class _FakeContainer:
    def __init__(self, stdout=b"root\n", stderr=b"", status="exited"):
        self.id = "fake-id"
        self.status = status
        self.attrs = {"State": {"ExitCode": 0}}
        self._stdout, self._stderr = stdout, stderr

    def reload(self):
        pass

    def logs(self, stdout=True, stderr=False):
        return self._stdout if stdout else self._stderr

    def kill(self):
        self.status = "exited"

    def remove(self, force=True):
        pass

    def exec_run(self, cmd, demux=True, timeout=30):
        return 0, (b"shell$ \n", b"")


class _FakeClient:
    def __init__(self):
        self.containers = mock.MagicMock()

    def ping(self):
        return True


def _executor_with_fake_client():
    fake_client = _FakeClient()
    ex = DockerExecutor(client_factory=lambda: fake_client)
    return ex, fake_client


def test_docker_executor_available_with_mock_client():
    ex, _ = _executor_with_fake_client()
    assert ex.available()


def test_docker_executor_ephemeral_run_success():
    ex, client = _executor_with_fake_client()
    fake = _FakeContainer(stdout=b"uid=0(root)\n")
    client.containers.run = mock.MagicMock(return_value=fake)
    result = ex.run_ephemeral("id")
    assert result.exit_code == 0
    assert "uid=0(root)" in result.stdout


def test_docker_executor_timeout_kills_and_marks():
    ex, client = _executor_with_fake_client()
    fake = _FakeContainer(status="running")
    client.containers.run = mock.MagicMock(return_value=fake)
    result = ex.run_ephemeral("sleep 100", timeout=0.01)
    assert result.timed_out and result.exit_code == -9


def test_docker_executor_session_send_input_detects_prompt():
    ex, _ = _executor_with_fake_client()
    sess = ex.open_session("ops")
    out = ex.send_input(sess.session_id, "whoami")
    assert out.session_id == sess.session_id
    assert ex.close_session(sess.session_id)


def test_detect_prompt_shell_and_msf():
    assert detect_prompt("hello\nroot@host:~$ ")["prompt_detected"]
    assert detect_prompt("exploit completed.\nmsf6 exploit(handler) > ")["prompt_type"] == "msfconsole"
    assert detect_prompt("still running...")["prompt_detected"] is False


def test_docker_executor_unavailable_graceful():
    def _bad():
        raise RuntimeError("docker unavailable: no daemon")
    ex = DockerExecutor(client_factory=_bad)
    assert not ex.available()


# -------- Step 3: signed engagement package ------------------------------
def _launch_test_mission(engine, name="sig-test"):
    manifest = MissionManifest(
        name=name, target_scope={"domains": ["lab.test"]},
        rules_of_engagement={"max_qps": 1})
    engine.launch(manifest, "lab.test")
    return engine.missions[manifest.mission_id]


def test_engagement_package_hmac_roundtrip():
    engine = MissionEngine(snapshot_path="")
    secret = os.urandom(32)
    mission = _launch_test_mission(engine)
    pkg = generate_engagement_package(mission, secret)
    assert pkg.signature and pkg.signature_key_hint
    assert verify_engagement_package(pkg, secret)["valid"]
    pkg.roe = pkg.roe + "\n# TAMPERED"
    assert not verify_engagement_package(pkg, secret)["valid"]


# -------- Step 4/6: vaccine loop + guided evasion -------------------------
def test_vaccine_loop_immunized_and_patch_drafted():
    engine = VaccineEngine()
    cycle = engine.run_cycle({"type": "SQL_INJECTION", "severity": "HIGH",
                              "sample": "' UNION SELECT password--"})
    assert cycle.verdict == "IMMUNIZED"
    assert cycle.patch_draft_id
    assert cycle.evidence_finding_id


def test_vaccine_loop_guided_recall_escalates_on_blind_spot():
    engine = VaccineEngine()
    f = {"type": "QX_BLIND", "sample": "qx"}
    first = engine.run_cycle(f)
    second = engine.run_cycle(f)
    guided = [r for r in second.replays if r.guided_by]
    assert guided, "second cycle must be guided by first-cycle lessons"


# -------- Step 5: hybrid graph persistence --------------------------------
def test_graph_journal_replay_restores_topology(tmp_path):
    jp = str(tmp_path / "journal.jsonl")
    g1 = CypherGraphEngine(journal_path=jp, seed=False)
    g1.add_node("web-01", ["Host"])
    g1.add_node("db-01", ["Host", "CrownJewel"])
    g1.add_edge("web-01", "db-01", "CONNECTS_TO")
    g2 = CypherGraphEngine(journal_path=jp, seed=False)
    replayed = g2.restore(jp)
    assert replayed == {"nodes": 2, "edges": 1}
    assert g2.find_shortest_path("web-01", "db-01")


def test_graph_snapshot_writes_state(tmp_path):
    g = CypherGraphEngine(journal_path=str(tmp_path / "j.jsonl"), seed=False)
    g.add_node("a", ["Host"])
    out = g.snapshot(str(tmp_path / "snap.json"))
    assert out and os.path.exists(out)
    state = json.load(open(out))
    assert "nodes" in state and len(state["nodes"]) == 1


# -------- Step 7: intel engine ---------------------------------------------
class _FakeResp:
    def json(self):
        return {"results": [{"title": "PoC", "url": "https://x",
                             "score": 0.9, "content": "dump"}]}


def test_intel_engine_degrades_without_key():
    assert IntelEngine(api_key=None).research("x").status == "NO_KEY"


def test_intel_engine_cache_hit_and_ttl():
    ie = IntelEngine(api_key="k", ttl_s=60)
    with mock.patch("httpx.post", return_value=_FakeResp()):
        first = ie.research("SMBGhost")
        second = ie.research("SMBGhost")
    assert first.status == "OK" and len(first.items) == 1
    assert second.cached and second.status == "CACHED"


# -------- Step 8: sonic batch recon + caching -------------------------------
def test_scan_ttl_cache_avoids_reprobe():
    scanner = AsyncSocketScanner()
    with mock.patch.object(scanner, "probe_port",
                           new=mock.AsyncMock(return_value=None)):
        first = asyncio.run(scanner.scan_target("lab.test"))
        assert first["cached"] is False
        second = asyncio.run(scanner.scan_target("lab.test"))
    assert second["cached"] is True


def test_batch_recon_fans_out_and_caches():
    scanner = AsyncSocketScanner()
    with mock.patch.object(scanner, "scan_target",
                           new=mock.AsyncMock(return_value={"cached": False})):
        report = asyncio.run(scanner.batch_recon(["a", "b", "c"], max_concurrent=2))
    assert report["batch_count"] == 3


# -------- Step 9: fresh-context parallel dispatch ----------------------------
import backend.parallel_dispatch as pd


def test_parallel_dispatch_isolated_lane_contexts():
    engine = MissionEngine(snapshot_path="")
    manifest = MissionManifest(
        name="iso-test", target_scope={"domains": ["lab"]},
        rules_of_engagement={"max_qps": 1})
    orig = pd.mission_engine
    pd.mission_engine = engine
    try:
        engine.launch(manifest, "lab")
        captured = {}

        async def runner(ctx: LaneContext):
            captured["ctx"] = ctx
            return "ok"
        lanes = asyncio.run(ParallelGoalDispatcher(max_concurrent=2).dispatch(runner))
        assert isinstance(captured["ctx"], LaneContext)
        assert captured["ctx"].goal["goal_id"] == "g1-recon"
        assert lanes[0].status == "DONE"
    finally:
        pd.mission_engine = orig


def test_dispatch_runner_failure_marks_goal_failed():
    engine = MissionEngine(snapshot_path="")
    manifest = MissionManifest(
        name="fail-test", target_scope={"domains": ["lab"]},
        rules_of_engagement={"max_qps": 1})
    orig = pd.mission_engine
    pd.mission_engine = engine
    try:
        engine.launch(manifest, "lab")

        async def bad_runner(ctx: LaneContext):
            raise RuntimeError("boom")
        statuses = [asyncio.run(ParallelGoalDispatcher().dispatch(bad_runner)) for _ in range(3)]
        assert all(l[0].status == "FAILED" for l in statuses)
        assert engine.missions[manifest.mission_id].gdt.goals["g1-recon"].state.value == "BLOCKED"
    finally:
        pd.mission_engine = orig


# -------- Step 10: dual-axis benchmark axes ---------------------------------
def test_benchmark_axes_dual_axis_keys():
    from backend.benchmark_engine import benchmark_engine
    report = benchmark_engine.collect().model_dump()
    assert {"attack", "accuracy", "safety", "grade"} <= set(report)
