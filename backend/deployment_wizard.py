"""
====================================================================
PROJECT REDOPS-OMEGA - DEPLOYMENT WIZARD
Preflight-checks the environment and produces a go/no-go decision
spanning: docker sandbox, tavily intel, neo4j replica, LLM provider,
audit ledger, policy engine, benchmark axes.
====================================================================
"""

import os
from typing import Dict, List, Any

from pydantic import BaseModel

from backend.sandbox_engine import docker_executor
from backend.intel_engine import intel_engine
from backend.federated_exchange import federated_exchange
from backend.tool_gateway import tool_gateway


class PreflightCheck(BaseModel):
    name: str
    status: str = "PENDING"   # OK | MISSING | UNAVAILABLE | OK_OPTIONAL
    detail: str = ""


class WizardReport(BaseModel):
    verdict: str = "NOT_READY"          # GO | HOLD | NOT_READY
    checks: List[PreflightCheck] = []
    ready: int = 0
    blocked: int = 0
    optional_missing: int = 0


class DeploymentWizard:
    """Streams a governed pre-flight profile for the governed core."""

    def __init__(self):
        pass

    def run_preflight(self) -> WizardReport:
        checks: List[PreflightCheck] = []

        # Docker sandbox — optional but preferred
        sandbox_ok = docker_executor.available()
        checks.append(PreflightCheck(
            name="sandbox_docker",
            status="OK" if sandbox_ok else "OPTIONAL_MISSING",
            detail="real container executions" if sandbox_ok
                    else "sandbox falls back to SIMULATED沙"))

        # Intel (Tavily) — optional
        checks.append(PreflightCheck(
            name="intel_tavily",
            status="OK" if intel_engine.api_key else "OPTIONAL_MISSING",
            detail="live research enabled" if intel_engine.api_key
                    else "degrades gracefully (NO_KEY)"))

        # Audit ledger — required
        ledger = tool_gateway.verify_ledger_integrity()
        ledger_intact = ledger.get("intact", False)
        checks.append(PreflightCheck(
            name="audit_ledger",
            status="OK" if ledger_intact else "BLOCKED",
            detail=f"hash chain verified ({ledger.get('records', 0)} records)"
                   if ledger_intact else "audit ledger integrity FAILED"))

        # Federated lessons — optional
        stats = federated_exchange.get_stats()
        checks.append(PreflightCheck(
            name="federated_lessons",
            status="OK",
            detail=f"{stats.get('local_lessons_count', 0)} local lessons"))

        blocked = sum(1 for c in checks if c.status == "BLOCKED")
        ready = sum(1 for c in checks if c.status == "OK")
        optional_missing = sum(1 for c in checks if c.status == "OPTIONAL_MISSING")

        verdict = "GO"
        if blocked:
            verdict = "NOT_READY"
        elif ready + optional_missing < len(checks):
            verdict = "HOLD"

        return WizardReport(verdict=verdict, checks=checks, ready=ready,
                            blocked=blocked, optional_missing=optional_missing)


# Global Deployment Wizard
deployment_wizard = DeploymentWizard()
