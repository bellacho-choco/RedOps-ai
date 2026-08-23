"""PLAN Step 16: Omega Pipeline Runner — one-command flagship."""
import asyncio
import json
import os

import pytest

from backend.omega_runner import OmegaRunner


@pytest.fixture(scope="module")
def runner():
    return OmegaRunner()


def test_full_pipeline_localhost(runner):
    report = asyncio.run(runner.run("127.0.0.1", export_report=True))
    stages = {s.stage: s.status for s in report.stages}
    expected = ["preflight_health", "governed_mission", "environment_model",
                "attack_path_reasoning", "witness_export", "claim_validation",
                "composite_scorecard"]
    for stage in expected:
        assert stage in stages, f"missing stage {stage}"
    assert stages["preflight_health"] == "OK"
    assert report.mission_id is not None
    assert report.mission_status.startswith("COMPLETED")
    assert report.witness_valid is True
    assert "gsi" in report.scorecard and "benchmark" in report.scorecard
    assert report.report_path and os.path.exists(report.report_path)
    data = json.load(open(report.report_path))
    assert data["run_id"] == report.run_id


def test_preflight_checks_all_engines(runner):
    from backend.omega_runner import OmegaRunReport
    rep = OmegaRunReport(target="x")
    assert runner._stage_preflight(rep) is True
    assert rep.stages[0].detail["agents_online"] is True
