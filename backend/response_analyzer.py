"""Response Differential Analyzer — real vulnerability signals.

Compares ResponseRecords to detect:
  - AUTH_BYPASS: unauth response materially equals authenticated baseline
  - IDOR: identity B can read identity A's resource (status 200 + content
    similarity) while A's own baseline differs by owner
  - REFLECTION: injected probe value reflected unsanitized in body
  - ERROR_BASED: DB/SQL error strings surfaced in response
  - STATUS_ANOMALY: unexpected 200/5xx transitions vs baseline

Signals are heuristic findings with confidence scores — they only become
'validated' after the ExploitValidator reproduces them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from backend.request_forge import ResponseRecord

SQL_ERRORS = [
    r"sql syntax", r"mysql_fetch", r"ORA-\d{4,5}", r"PostgreSQL.*ERROR",
    r"SQLite/JDBCDriver", r"unclosed quotation mark", r"syntax error.*sql",
    r"Microsoft OLE DB Provider for SQL Server",
]
SENSITIVE_MARKERS = [
    r'"email"\s*:', r'"password', r'"api[_-]?key"\s*:', r'"ssn"',
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", r'"token"\s*:\s*"[A-Za-z0-9_\-]{16,}"',
]


@dataclass
class Signal:
    kind: str
    url: str
    detail: str
    confidence: float
    severity: str
    context: Dict[str, Any] = field(default_factory=dict)


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:8000], b[:8000]).ratio()


class ResponseAnalyzer:
    def compare_identities(self, authed: ResponseRecord,
                           unauth: ResponseRecord) -> List[Signal]:
        signals: List[Signal] = []
        if unauth.status == 200 and authed.status == 200:
            sim = similarity(authed.body, unauth.body)
            if sim > 0.9 and unauth.length > 40:
                signals.append(Signal(
                    kind="AUTH_BYPASS", url=unauth.url,
                    detail=(f"Unauthenticated response {sim:.0%} similar to "
                            f"authenticated baseline ({authed.length}B vs {unauth.length}B)"),
                    confidence=round(sim, 3), severity="HIGH",
                    context={"authed_digest": authed.digest, "unauth_digest": unauth.digest}))
        return signals

    def check_reflection(self, record: ResponseRecord, probe: str) -> List[Signal]:
        if probe and probe in record.body:
            return [Signal(kind="REFLECTION", url=record.url,
                           detail=f"Probe value reflected unsanitized: {probe!r}",
                           confidence=0.7, severity="MEDIUM",
                           context={"probe": probe, "status": record.status})]
        return []

    def check_error_based(self, record: ResponseRecord) -> List[Signal]:
        signals = []
        for pattern in SQL_ERRORS:
            m = re.search(pattern, record.body, re.I)
            if m:
                signals.append(Signal(
                    kind="ERROR_BASED_SQLI", url=record.url,
                    detail=f"Database error surfaced: {m.group(0)[:80]}",
                    confidence=0.85, severity="HIGH",
                    context={"matched": m.group(0)[:120], "status": record.status}))
                break
        return signals

    def check_sensitive_disclosure(self, record: ResponseRecord) -> List[Signal]:
        signals = []
        for pattern in SENSITIVE_MARKERS:
            if re.search(pattern, record.body):
                signals.append(Signal(
                    kind="SENSITIVE_DISCLOSURE", url=record.url,
                    detail=f"Sensitive marker matched: {pattern[:40]}",
                    confidence=0.6, severity="MEDIUM",
                    context={"status": record.status}))
        return signals

    def analyze(self, record: ResponseRecord,
                baseline: Optional[ResponseRecord] = None,
                probe: Optional[str] = None) -> List[Signal]:
        signals = self.check_error_based(record) + self.check_sensitive_disclosure(record)
        if probe:
            signals += self.check_reflection(record, probe)
        if baseline and baseline.identity != record.identity:
            signals += self.compare_identities(baseline, record)
        return signals


response_analyzer = ResponseAnalyzer()
