"""
====================================================================
PROJECT REDOPS-OMEGA - OMEGA PIPELINE RUNNER (FLAGSHIP)
One-command cognitive pipeline: preflight health -> governed mission
launch -> environment model -> attack-path reasoning -> witness
export -> claim validation -> composite scorecard. Blueprint Phase 4.
====================================================================
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.agents import swarm_matrix
from backend.attack_path_engine import attack_path_engine
from backend.benchmark_engine import benchmark_engine
from backend.cypher_engine import graph_engine
from backend.evidence_engine import evidence_engine, FindingState
from backend.gsi_engine import gsi_engine
from backend.mission_engine import (
    mission_engine, generate_engagement_package, verify_engagement_package)
from backend.skills_engine import skills_engine
from backend.tool_gateway import tool_gateway


class PipelineStage(BaseModel):
    stage: str
    status: str = "PENDING"          # OK / WARN / FAILED
    elapsed_ms: float = 0.0
    detail: Dict[str, Any] = Field(default_factory=dict)


class OmegaRunReport(BaseModel):
    run_id: str = Field(default_factory=lambda: f"omega-{uuid.uuid4().hex[:8]}")
    target: str
    started_at: float = Field(default_factory=time.time)
    stages: List[PipelineStage] = Field(default_factory=list)
    mission_id: Optional[str] = None
    mission_status: str = "NOT_LAUNCHED"
    witness_valid: Optional[bool] = None
    scorecard: Dict[str, Any] = Field(default_factory=dict)
    report_path: Optional[str] = None


class OmegaRunner:
    """Orchestrates the full REDOPS-Ω pipeline as one auditable run."""

    REPORTS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "reports", "omega")

    def __init__(self):
        os.makedirs(self.REPORTS_DIR, exist_ok=True)

    # ---------------- Stage 0: preflight health ----------------------
    def _stage_preflight(self, report: OmegaRunReport) -> bool:
        checks = {
            "skills_indexed": len(skills_engine.skills) > 0,
            "graph_engine": graph_engine is not None,
            "gateway_ledger": isinstance(tool_gateway.audit_ledger, list),
            "agents_online": len(swarm_matrix.agents) == 6,
        }
        ok = all(checks.values())
        report.stages.append(PipelineStage(
            stage="preflight_health", status="OK" if ok else "FAILED",
            detail=checks))
        return ok

    # ---------------- Stage 1: governed mission ----------------------
    async def _stage_mission(self, report: OmegaRunReport) -> None:
        t0 = time.time()
        await swarm_matrix.overlord.execute_mission(report.target)
        mission = mission_engine.get_active()
        if mission:
            report.mission_id = mission.manifest.mission_id
            report.mission_status = mission.status
        report.stages.append(PipelineStage(
            stage="governed_mission",
            status="OK" if mission and mission.status.startswith("COMPLETED") else "WARN",
            elapsed_ms=round((time.time() - t0) * 1000, 2),
            detail={"mission_id": report.mission_id,
                    "status": report.mission_status}))

    # ---------------- Stage 2: environment model ---------------------
    def _stage_world_model(self, report: OmegaRunReport) -> None:
        state = graph_engine.get_full_graph_state()
        report.stages.append(PipelineStage(
            stage="environment_model", status="OK",
            detail={"nodes": state.get("node_count", len(state.get("nodes", []))),
                    "edges": state.get("edge_count", len(state.get("edges", [])))}))

    # ---------------- Stage 3: attack-path reasoning -----------------
    def _stage_attack_paths(self, report: OmegaRunReport) -> None:
        paths = attack_path_engine.enumerate_paths()
        top = sorted(paths, key=lambda p: p.score.total(), reverse=True)[:3]
        report.stages.append(PipelineStage(
            stage="attack_path_reasoning",
            status="OK" if paths else "WARN",
            detail={"paths_enumerated": len(paths),
                    "top_scores": [round(p.score.total(), 2) for p in top]}))

    # ---------------- Stage 4: witness export ------------------------
    def _stage_witness(self, report: OmegaRunReport) -> None:
        mission = mission_engine.get(report.mission_id) if report.mission_id else None
        if not mission:
            report.stages.append(PipelineStage(
                stage="witness_export", status="FAILED",
                detail={"reason": "no mission"}))
            return
        secret = b"omega-runner-witness-key"
        package = generate_engagement_package(mission, secret)
        verification = verify_engagement_package(package, secret)
        report.witness_valid = verification["valid"]
        report.stages.append(PipelineStage(
            stage="witness_export",
            status="OK" if verification["valid"] else "FAILED",
            detail={"package_id": verification["package_id"],
                    "tamper_evident": verification["valid"]}))

    # ---------------- Stage 5: claim validation ----------------------
    def _stage_claims(self, report: OmegaRunReport) -> None:
        findings = list(evidence_engine.findings.values())
        unproven = [f.title for f in findings
                    if f.state != FindingState.VALIDATED or not f.evidence]
        report.stages.append(PipelineStage(
            stage="claim_validation",
            status="OK" if not unproven else "WARN",
            detail={"findings": len(findings),
                    "unproven_claims": unproven}))

    # ---------------- Stage 6: composite scorecard -------------------
    def _stage_scorecard(self, report: OmegaRunReport) -> None:
        from backend.synthesis_engine import issue_trust_certificate
        bench = benchmark_engine.collect()
        gsi = gsi_engine.score()
        report.scorecard = {
            "gsi": {"score": gsi.score, "grade": gsi.grade,
                    "attack_accuracy": gsi.attack_accuracy,
                    "safety_compliance": gsi.safety_compliance,
                    "defense_readiness": gsi.defense_readiness,
                    "lessons_depth": gsi.lessons_depth},
            "benchmark": {"grade": bench.grade,
                          "publishable": bench.publishable,
                          "policy_compliance_rate": bench.safety.policy_compliance_rate,
                          "scope_leaks": bench.safety.scope_leaks},
        }
        # Signed trust certificate over measured claims only (Phase 4)
        cert = issue_trust_certificate(
            subject=report.run_id,
            claims={"mission_status": report.mission_status,
                    "gsi_grade": gsi.grade,
                    "witness_valid": report.witness_valid,
                    "publishable": bench.publishable},
            evidence_refs=[report.report_path] if report.report_path else [])
        report.scorecard["trust_certificate"] = {
            "certificate_id": cert.certificate_id,
            "signature": cert.signature,
            "valid": cert.verify()}
        report.stages.append(PipelineStage(
            stage="composite_scorecard", status="OK",
            detail=report.scorecard))

    # ---------------- Run --------------------------------------------
    async def run(self, target: str = "127.0.0.1",
                  export_report: bool = True) -> OmegaRunReport:
        report = OmegaRunReport(target=target)
        if not self._stage_preflight(report):
            return report
        await self._stage_mission(report)
        self._stage_world_model(report)
        self._stage_attack_paths(report)
        self._stage_witness(report)
        self._stage_claims(report)
        self._stage_scorecard(report)
        if export_report:
            report.report_path = self._export(report)
        return report

    def _export(self, report: OmegaRunReport) -> str:
        path = os.path.join(self.REPORTS_DIR, f"{report.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)
        return path


omega_runner = OmegaRunner()
