"""
====================================================================
PROJECT REDOPS-OMEGA - TRUST CERTIFICATE & SKILL AUTO-SYNTHESIS
Signed trust certificates over pipeline runs, plus controlled skill
synthesis from regression-tested strategy memory. Drafts land in a
staging area pending human approval — never auto-promoted to the
live index. Blueprint Phase 4 (controlled self-improvement).
====================================================================
"""

import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.skills_engine import RedOpsSkillEngine
from backend.strategy_memory import strategy_memory

_CERT_SECRET = os.environ.get("REDOPS_TRUST_SECRET", "redops-trust-dev-key").encode()

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING_DIR = os.path.join(WORKSPACE_ROOT, "skills", "staging")


# ====================================================================
# TRUST CERTIFICATE
# ====================================================================
class TrustCertificate(BaseModel):
    certificate_id: str = Field(default_factory=lambda: f"cert-{uuid.uuid4().hex[:10]}")
    issued_at: float = Field(default_factory=time.time)
    subject: str                       # e.g. omega run id
    claims: Dict[str, Any]             # measured, verifiable claims only
    evidence_refs: List[str] = Field(default_factory=list)
    signature: str = ""

    def signing_body(self) -> str:
        return json.dumps({"subject": self.subject, "claims": self.claims,
                           "evidence_refs": self.evidence_refs,
                           "issued_at": self.issued_at}, sort_keys=True)

    def sign(self) -> None:
        self.signature = hmac.new(_CERT_SECRET, self.signing_body().encode(),
                                  hashlib.sha256).hexdigest()

    def verify(self) -> bool:
        expected = hmac.new(_CERT_SECRET, self.signing_body().encode(),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)


def issue_trust_certificate(subject: str,
                            claims: Dict[str, Any],
                            evidence_refs: Optional[List[str]] = None) -> TrustCertificate:
    cert = TrustCertificate(subject=subject, claims=claims,
                            evidence_refs=evidence_refs or [])
    cert.sign()
    return cert


# ====================================================================
# SKILL AUTO-SYNTHESIS
# ====================================================================
class SynthesisResult(BaseModel):
    status: str                        # STAGED / REJECTED / NO_CANDIDATES
    skill_name: Optional[str] = None
    staging_path: Optional[str] = None
    validation: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class SkillSynthesisEngine:
    """
    Controlled self-improvement: turns regression-tested strategy lessons
    into SKILL.md drafts. Every draft is validated by the same PyYAML
    parser the live index uses, then staged for human approval — the
    production control plane is never rewritten autonomously.
    """

    MIN_OCCURRENCES = 2

    def __init__(self, staging_dir: Optional[str] = None):
        self.staging_dir = staging_dir or STAGING_DIR

    def candidates(self) -> List[Dict[str, Any]]:
        approved = strategy_memory.approved_strategies()
        return [l for l in approved
                if l.get("occurrences", 0) >= self.MIN_OCCURRENCES]

    def synthesize(self, lesson: Optional[Dict[str, Any]] = None) -> SynthesisResult:
        if lesson is None:
            cands = self.candidates()
            if not cands:
                return SynthesisResult(status="NO_CANDIDATES",
                                       reason="no regression-tested strategy "
                                              "meets the occurrence threshold")
            lesson = cands[0]
        name = self._skill_name(lesson["pattern"])
        content = self._render_skill_md(name, lesson)
        validation = self._validate(content)
        if not validation["frontmatter_valid"]:
            return SynthesisResult(status="REJECTED", skill_name=name,
                                   validation=validation,
                                   reason="draft failed parser regression")
        path = self._stage(name, content)
        return SynthesisResult(status="STAGED", skill_name=name,
                               staging_path=path, validation=validation)

    @staticmethod
    def _skill_name(pattern: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", pattern.lower()).strip("-")
        return f"learned-{slug[:40] or 'strategy'}"

    @staticmethod
    def _render_skill_md(name: str, lesson: Dict[str, Any]) -> str:
        tags = lesson.get("context_tags", [])
        tag_lines = "\n".join(f"    - {t}" for t in tags) or "    - learned"
        return f"""---
name: {name}
description: >-
  Auto-synthesized playbook from regression-tested campaign outcome:
  {lesson['pattern'][:120]}
metadata:
  tags:
{tag_lines}
status: PENDING_APPROVAL
source: strategy-memory
---

# {name}

Synthesized from {lesson.get('occurrences', 1)} regression-tested successful
outcome(s) in prior campaigns.

## Playbook

1. Reproduce the conditions matching pattern: `{lesson['pattern']}`
2. Apply the validated strategy that previously produced SUCCESS.
3. Anchor evidence tokens for every claim before reporting.

## Provenance

- lesson_id: {lesson.get('lesson_id', 'n/a')}
- outcome: {lesson.get('outcome', 'SUCCESS')}
- regression_tested: {lesson.get('regression_tested', False)}
"""

    @staticmethod
    def _validate(content: str) -> Dict[str, Any]:
        """Regression gate: draft must parse under the live YAML parser."""
        probe = RedOpsSkillEngine.__new__(RedOpsSkillEngine)
        fm = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not fm:
            return {"frontmatter_valid": False, "reason": "no frontmatter"}
        parsed = RedOpsSkillEngine._parse_yaml_frontmatter(fm.group(1))
        valid = isinstance(parsed, dict) and bool(parsed.get("name"))
        return {"frontmatter_valid": bool(valid),
                "parsed_name": (parsed or {}).get("name"),
                "tags_extracted": RedOpsSkillEngine._extract_nested_tags(parsed or {})}

    def _stage(self, name: str, content: str) -> str:
        path = os.path.join(self.staging_dir, name)
        os.makedirs(path, exist_ok=True)
        skill_path = os.path.join(path, "SKILL.md")
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)
        return skill_path

    def list_staged(self) -> List[Dict[str, Any]]:
        if not os.path.isdir(self.staging_dir):
            return []
        return [{"skill": d, "status": "PENDING_APPROVAL"}
                for d in sorted(os.listdir(self.staging_dir))
                if os.path.isdir(os.path.join(self.staging_dir, d))]


synthesis_engine = SkillSynthesisEngine()
