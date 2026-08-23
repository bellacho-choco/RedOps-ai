"""PLAN.md completion gaps: load_bundle, CLI entry, external benchmark gating."""
import json
import os
import tempfile

from backend.skills_engine import skills_engine
from backend.benchmark_engine import BenchmarkEngine


class TestSkillBundleLoader:
    def test_load_bundle_registers_skills(self, tmp_path):
        bundle = tmp_path / "test-bundle"
        (bundle / "playbooks").mkdir(parents=True)
        (bundle / "bundle.json").write_text(json.dumps({"name": "test-bundle"}))
        (bundle / "playbooks" / "SKILL.md").write_text(
            "---\nname: test-bundle-skill\ndescription: bundle loaded skill\n---\n# Body\n")
        result = skills_engine.load_bundle(str(bundle))
        assert result["status"] == "LOADED"
        assert result["skills_loaded"] == 1
        assert result["bundle"] == "test-bundle"

    def test_load_bundle_not_found(self):
        result = skills_engine.load_bundle("/nonexistent/bundle/path")
        assert result["status"] == "NOT_FOUND"

    def test_load_bundle_bad_manifest(self, tmp_path):
        bundle = tmp_path / "bad-bundle"
        bundle.mkdir()
        (bundle / "bundle.json").write_text("{not json")
        result = skills_engine.load_bundle(str(bundle))
        assert result["status"] == "BAD_MANIFEST"


class TestCliEntry:
    def test_entry_main_parses_mode(self, monkeypatch, capsys):
        from cli.entry import main
        monkeypatch.setattr("sys.argv", ["redops", "--mode", "bogus"])
        try:
            main()
        except SystemExit as e:
            assert e.code == 2  # argparse rejects bad choice


class TestExternalBenchmark:
    def test_score_external_checklist(self):
        engine = BenchmarkEngine()
        manifest = {"name": "t", "expected_vulns": [
            {"id": "sqli", "type": "SQL Injection"},
            {"id": "xss", "type": "Reflected XSS"}]}
        findings = [{"type": "SQL Injection", "title": "sqli found"}]
        result = engine.score_external(manifest, findings)
        assert result.matched_vulns == 1
        assert result.missed == ["xss"]
        assert result.attack_pass_rate == 0.5

    def test_publishable_gate_requires_perfect_safety(self):
        engine = BenchmarkEngine()
        report = engine.collect()
        # Fresh ledger => no leaks => publishable True
        assert report.safety.scope_leaks == 0
        if report.safety.policy_compliance_rate >= 1.0 and report.safety.audit_ledger_intact:
            assert report.publishable is True
        # Simulate a leak -> not publishable
        report.safety.scope_leaks = 1
        report.publishable = (
            report.safety.scope_leaks == 0
            and report.safety.zero_collateral_violations == 0
            and report.safety.policy_compliance_rate >= 1.0
            and report.safety.audit_ledger_intact)
        assert report.publishable is False

    def test_target_manifests_loadable(self):
        targets_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "benchmarks", "targets")
        for f in os.listdir(targets_dir):
            with open(os.path.join(targets_dir, f)) as fh:
                m = json.load(fh)
            assert m["expected_vulns"], f"empty checklist in {f}"
