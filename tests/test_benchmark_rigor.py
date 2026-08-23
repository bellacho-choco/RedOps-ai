"""PLAN Step 13: reproducible benchmark rigor — determinism, traces, rot."""
import json
import os

from backend.benchmark_engine import BenchmarkEngine


MANIFEST = {"name": "test-target",
            "scope": {"domains": ["localhost"], "ports": [9]},
            "expected_vulns": [{"id": "sqli", "type": "SQL Injection"},
                               {"id": "xss", "type": "XSS"}]}
FINDINGS = [{"type": "SQL Injection", "title": "auth bypass"}]


class TestDeterministicReplay:
    def test_same_seed_same_score(self):
        eng = BenchmarkEngine()
        r1 = eng.score_external(MANIFEST, list(FINDINGS), seed=42)
        r2 = eng.score_external(MANIFEST, list(reversed(FINDINGS)), seed=42)
        assert r1.attack_pass_rate == r2.attack_pass_rate
        assert r1.matched_vulns == r2.matched_vulns == 1
        assert r1.missed == r2.missed == ["xss"]

    def test_trace_exported_jsonl(self):
        eng = BenchmarkEngine()
        r = eng.score_external(MANIFEST, list(FINDINGS), seed=7)
        assert r.trace_path and os.path.exists(r.trace_path)
        events = [json.loads(l) for l in open(r.trace_path)]
        assert events[0]["event"] == "run" and events[0]["seed"] == 7
        assert events[-1]["event"] == "score"
        os.remove(r.trace_path)


class TestRotDetection:
    def test_unhealthy_target_excluded_from_scoring(self):
        # Port 9 (discard) is closed on virtually every host
        health = BenchmarkEngine.health_check(MANIFEST, timeout=0.5)
        assert health["health"] == "UNHEALTHY"
        assert health["scored"] is False

    def test_healthy_target_scored(self):
        health = BenchmarkEngine.health_check(
            MANIFEST, probe=lambda h, p, t: (True, "mock-ok"))
        assert health["health"] == "HEALTHY"
        assert health["scored"] is True

    def test_probe_error_flagged_not_crashed(self):
        def boom(h, p, t):
            raise RuntimeError("probe exploded")
        health = BenchmarkEngine.health_check(MANIFEST, probe=boom)
        assert health["health"] == "UNHEALTHY"
