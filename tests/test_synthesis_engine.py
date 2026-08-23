"""PLAN Step 17: Trust Certificate + Skill Auto-Synthesis."""
import os

from backend.synthesis_engine import (SkillSynthesisEngine,
                                      issue_trust_certificate)
from backend.strategy_memory import strategy_memory


class TestTrustCertificate:
    def test_sign_and_verify(self):
        cert = issue_trust_certificate("omega-test", {"gsi_grade": "B"})
        assert cert.verify() is True

    def test_tamper_detected(self):
        cert = issue_trust_certificate("omega-test", {"gsi_grade": "B"})
        cert.claims["gsi_grade"] = "A"   # attacker inflates the grade
        assert cert.verify() is False

    def test_deterministic_signature(self):
        c1 = issue_trust_certificate("s", {"a": 1})
        c2 = issue_trust_certificate("s", {"a": 1})
        c2.issued_at = c1.issued_at
        c2.sign()  # re-sign over the same body
        assert c1.signature == c2.signature


class TestSkillSynthesis:
    def _seed_lessons(self):
        strategy_memory.record_outcome(
            "SYNTH-TEST exploit chain on lab", "SUCCESS",
            tags=["web", "sqli"], regression_tested=True)
        strategy_memory.record_outcome(
            "SYNTH-TEST exploit chain on lab", "SUCCESS",
            tags=["web", "sqli"], regression_tested=True)

    def test_synthesize_stages_draft(self, tmp_path):
        self._seed_lessons()
        eng = SkillSynthesisEngine(staging_dir=str(tmp_path / "staging"))
        cands = [c for c in eng.candidates() if "synth-test" in c["pattern"]]
        assert cands
        result = eng.synthesize(lesson=cands[0])
        assert result.status == "STAGED", result.reason
        assert result.validation["frontmatter_valid"] is True
        assert os.path.exists(result.staging_path)
        content = open(result.staging_path).read()
        assert "PENDING_APPROVAL" in content

    def test_no_candidates_clean_reject(self):
        eng = SkillSynthesisEngine()
        eng.MIN_OCCURRENCES = 10**9
        result = eng.synthesize()
        assert result.status == "NO_CANDIDATES"

    def test_staged_draft_not_in_live_index(self):
        from backend.skills_engine import skills_engine
        assert not any("staging" in k for k in skills_engine.skills)
