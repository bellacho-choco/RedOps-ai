"""
====================================================================
PROJECT REDOPS-OMEGA - SELF-HEALING ENGINE (PHASE III: 2040)
Automated defensive posture mitigation: converts SAST findings into
concrete, reviewable remediation patches. Blueprint Section 15 Phase III.

Generated patches are ALWAYS drafts — they are attached to the Evidence
Engine as remediation artifacts and require human review before apply.
====================================================================
"""

import re
import time
import uuid
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.sast_analyzer import sast_auditor
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory


class PatchDraft(BaseModel):
    patch_id: str = Field(default_factory=lambda: f"patch-{uuid.uuid4().hex[:8]}")
    finding_type: str
    severity: str
    source: str
    vulnerable_snippet: str           # redacted view of the offending code
    patched_code: str                 # synthesized replacement
    rationale: str
    confidence: float = 0.8
    status: str = "DRAFT"             # DRAFT | APPROVED | APPLIED | REJECTED
    created_at: float = Field(default_factory=time.time)


# --------------------------------------------------------------------
# Remediation synthesizers per finding class. Each returns the patched
# replacement code + a human-readable rationale.
# --------------------------------------------------------------------
def _fix_eval_exec(snippet: str) -> Dict[str, str]:
    inner = re.sub(r"(?i)^\s*(eval|exec)\s*\(", "", snippet).rstrip().rstrip(")")
    return {
        "patched_code": (
            f"# UNSAFE eval/exec removed by REDOPS-OMEGA Self-Healing Engine\n"
            f"# Original intent must be re-expressed with a safe dispatcher:\n"
            f"SAFE_DISPATCH = {{}}  # map allowed operations to callables\n"
            f"result = SAFE_DISPATCH.get({inner.strip()!r}, lambda: None)()"
        ),
        "rationale": "Dynamic eval/exec enables arbitrary code execution; replace "
                     "with an explicit allow-list dispatch table.",
    }


def _fix_sql_concat(snippet: str) -> Dict[str, str]:
    return {
        "patched_code": (
            f"# SQL string concatenation removed by REDOPS-OMEGA Self-Healing Engine\n"
            f"# Original: {snippet[:80]}\n"
            f"cursor.execute(\"<QUERY> WHERE col = %s\", (user_input,))  # parameterized"
        ),
        "rationale": "String-built SQL is injectable; parameter binding separates "
                     "code from data and neutralizes injection payloads.",
    }


def _fix_secret(finding_type: str, snippet: str) -> Dict[str, str]:
    return {
        "patched_code": (
            f"# Hardcoded {finding_type} removed by REDOPS-OMEGA Self-Healing Engine\n"
            f"import os\n"
            f"SECRET = os.environ[\"{finding_type}\"]  # injected via secrets manager"
        ),
        "rationale": f"Embedded {finding_type} in source control is a credential leak; "
                     "rotate the exposed value immediately and source it from the "
                     "environment / vault at runtime.",
    }


def _fix_generic(finding_type: str, snippet: str) -> Dict[str, str]:
    return {
        "patched_code": (
            f"# Finding {finding_type} flagged by REDOPS-OMEGA Self-Healing Engine\n"
            f"# Manual remediation required. Offending sample: {snippet[:60]}"
        ),
        "rationale": "No deterministic rewrite exists for this class; requires "
                     "engineer review with the attached context.",
    }


class SelfHealingEngine:
    """
    Scans code artifacts via the SAST auditor and synthesizes remediation
    patch drafts. Every draft is anchored into the Evidence Engine and the
    outcome is recorded into strategy memory so the remediation playbook
    itself improves over campaigns.
    """
    def __init__(self):
        self.drafts: Dict[str, PatchDraft] = {}

    def synthesize_patch(self, finding: Dict[str, Any]) -> PatchDraft:
        ftype = finding.get("type", "UNKNOWN")
        snippet = finding.get("sample", "")
        severity = finding.get("severity", "MEDIUM")

        if ftype == "UNSAFE_EVAL_EXEC":
            fix = _fix_eval_exec(snippet)
        elif ftype == "SQL_CONCATENATION":
            fix = _fix_sql_concat(snippet)
        elif ftype in ("AWS_ACCESS_KEY", "JWT_BEARER_TOKEN", "GENERIC_PRIVATE_KEY",
                       "GITHUB_PAT", "SLACK_WEBHOOK", "GENERIC_API_KEY"):
            fix = _fix_secret(ftype, snippet)
            severity = max(severity, "HIGH", key=lambda s: ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(s))
        else:
            fix = _fix_generic(ftype, snippet)

        draft = PatchDraft(
            finding_type=ftype, severity=severity,
            source=finding.get("source", "unknown"),
            vulnerable_snippet=snippet, patched_code=fix["patched_code"],
            rationale=fix["rationale"],
            confidence=0.9 if ftype != "HIGH_ENTROPY_TOKEN" else 0.5,
        )
        self.drafts[draft.patch_id] = draft
        return draft

    def heal_buffer(self, content: str, source_name: str = "Buffer") -> Dict[str, Any]:
        """Full pipeline: scan -> synthesize -> anchor evidence -> record lesson."""
        findings = sast_auditor.analyze_buffer(content, source_name)
        drafts = [self.synthesize_patch(f) for f in findings]

        for d in drafts:
            evidence_engine.register_finding(
                f"Code flaw {d.finding_type} in {d.source}", d.source,
                "SELF-HEALING", d.severity)
            strategy_memory.record_outcome(
                f"remediate {d.finding_type} in {d.source}",
                "SUCCESS" if d.confidence >= 0.8 else "PENDING",
                tags=["self-healing", d.finding_type], regression_tested=False)

        return {
            "source": source_name,
            "findings": len(findings),
            "patch_drafts": [d.model_dump() for d in drafts],
        }

    def set_status(self, patch_id: str, status: str) -> Optional[PatchDraft]:
        draft = self.drafts.get(patch_id)
        if not draft:
            return None
        draft.status = status.upper()
        if draft.status == "APPLIED":
            strategy_memory.record_outcome(
                f"applied patch for {draft.finding_type}", "SUCCESS",
                tags=["self-healing", "applied"], regression_tested=True)
        return draft

    def get_stats(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for d in self.drafts.values():
            by_status[d.status] = by_status.get(d.status, 0) + 1
        return {"total_drafts": len(self.drafts), "by_status": by_status}


# Global Self-Healing Engine
self_healing_engine = SelfHealingEngine()
