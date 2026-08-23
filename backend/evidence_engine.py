"""
====================================================================
PROJECT REDOPS-OMEGA - EVIDENCE & VALIDATION ENGINE
Cryptographic Evidence Tokens, Confidence Scoring, False-Positive
Downgrading & Reproducible Test Script Synthesis. Blueprint Section 11.
====================================================================
"""

import hashlib
import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field


class FindingState(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"      # agent claim, no artifact yet
    POTENTIAL = "POTENTIAL"        # some signal, evidence incomplete
    VALIDATED = "VALIDATED"        # cryptographic evidence token anchored
    FALSE_POSITIVE = "FALSE_POSITIVE"  # execution metrics contradicted the claim


class EvidenceToken(BaseModel):
    token_id: str = Field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:10]}")
    finding_id: str
    agent: str
    artifact_type: str             # http_response | file_signature | scan_output | safe_hash
    artifact_digest: str           # sha256 of the raw artifact
    artifact_summary: str
    captured_at: float = Field(default_factory=time.time)

    @staticmethod
    def digest_artifact(artifact: Any) -> str:
        raw = artifact if isinstance(artifact, (str, bytes)) else json.dumps(artifact, sort_keys=True, default=str)
        if isinstance(raw, str):
            raw = raw.encode()
        return hashlib.sha256(raw).hexdigest()


class Finding(BaseModel):
    finding_id: str
    title: str
    severity: str = "MEDIUM"
    target: str
    agent: str
    state: FindingState = FindingState.HYPOTHESIS
    confidence: float = 0.2        # 0.0 - 1.0
    evidence: List[EvidenceToken] = Field(default_factory=list)
    repro_script: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# Confidence deltas for validation outcomes.
_EVIDENCE_BOOST = 0.35
_CONTRADICTION_PENALTY = 0.5


class EvidenceEngine:
    """
    Anchors every agent claim to verifiable artifacts. A finding only
    reaches VALIDATED when its expected evidence token materializes;
    contradictory execution metrics downgrade it for manual triage.
    """
    def __init__(self):
        self.findings: Dict[str, Finding] = {}

    def register_finding(self, title: str, target: str, agent: str,
                         severity: str = "MEDIUM") -> Finding:
        finding = Finding(
            finding_id=f"find-{uuid.uuid4().hex[:8]}",
            title=title, target=target, agent=agent, severity=severity.upper(),
        )
        self.findings[finding.finding_id] = finding
        return finding

    def attach_evidence(self, finding_id: str, agent: str, artifact: Any,
                        artifact_type: str = "scan_output",
                        summary: str = "") -> Optional[EvidenceToken]:
        finding = self.findings.get(finding_id)
        if not finding:
            return None
        token = EvidenceToken(
            finding_id=finding_id, agent=agent, artifact_type=artifact_type,
            artifact_digest=EvidenceToken.digest_artifact(artifact),
            artifact_summary=summary or str(artifact)[:160],
        )
        finding.evidence.append(token)
        finding.confidence = min(1.0, finding.confidence + _EVIDENCE_BOOST)

        if finding.confidence >= 0.7 and finding.state != FindingState.FALSE_POSITIVE:
            finding.state = FindingState.VALIDATED
            finding.repro_script = self._synthesize_repro(finding, token)
        elif finding.state == FindingState.HYPOTHESIS:
            finding.state = FindingState.POTENTIAL
        return token

    def report_contradiction(self, finding_id: str, reason: str) -> Optional[Finding]:
        """Execution metrics did not produce the expected evidence token."""
        finding = self.findings.get(finding_id)
        if not finding:
            return None
        finding.confidence = max(0.0, finding.confidence - _CONTRADICTION_PENALTY)
        finding.notes.append(f"FP signal: {reason}")
        if finding.confidence < 0.3:
            finding.state = FindingState.FALSE_POSITIVE
        else:
            finding.state = FindingState.POTENTIAL
        finding.notes.append("Downgraded; flagged for manual triage")
        return finding

    def verify_token(self, token_id: str, artifact: Any) -> bool:
        """Re-hash a fresh artifact to confirm an evidence token still holds."""
        for finding in self.findings.values():
            for token in finding.evidence:
                if token.token_id == token_id:
                    return token.artifact_digest == EvidenceToken.digest_artifact(artifact)
        return False

    def _synthesize_repro(self, finding: Finding, token: EvidenceToken) -> str:
        """Non-destructive verification snippet for the customer engineer."""
        host = finding.target.split("//")[-1].split("/")[0]
        return (
            f"# REDOPS-OMEGA Repro Script — {finding.finding_id}\n"
            f"# Finding: {finding.title} ({finding.severity})\n"
            f"# Safe, read-only verification. Evidence digest: {token.artifact_digest[:16]}...\n"
            f"curl -sS -o /dev/null -w '%{{http_code}} %{{header_json}}' \\\n"
            f"  --max-time 10 'http://{host}/'\n"
            f"# Expected artifact type: {token.artifact_type}\n"
        )

    def get_state_summary(self) -> Dict[str, Any]:
        states: Dict[str, int] = {}
        for f in self.findings.values():
            states[f.state.value] = states.get(f.state.value, 0) + 1
        return {
            "total_findings": len(self.findings),
            "by_state": states,
            "validated_ratio": round(
                states.get("VALIDATED", 0) / max(1, len(self.findings)), 3
            ),
        }


# Global Evidence Engine
evidence_engine = EvidenceEngine()
