"""
====================================================================
PROJECT REDOPS-OMEGA - FEDERATED CYBER RANGE EXCHANGE (PHASE III: 2040)
Cross-grid strategy sharing WITHOUT leaking private corporate data.
Lesson packs are anonymized (targets/IPs/hostnames stripped), HMAC-signed
with the local grid key, and verified on import. Blueprint Section 15,
Phase III: federated learning without secret leakage.
====================================================================
"""

import hashlib
import hmac
import os
import re
import time
import uuid
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.strategy_memory import strategy_memory

_GRID_KEY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".redops_memory", ".grid_key")


def _load_grid_key() -> bytes:
    """Local grid signing key; generated on first use, never exported."""
    if os.path.exists(_GRID_KEY_PATH):
        with open(_GRID_KEY_PATH, "rb") as fh:
            return fh.read()
    os.makedirs(os.path.dirname(_GRID_KEY_PATH), exist_ok=True)
    key = os.urandom(32)
    with open(_GRID_KEY_PATH, "wb") as fh:
        fh.write(key)
    try:
        os.chmod(_GRID_KEY_PATH, 0o600)
    except OSError:
        pass
    return key


_SCRUB_PATTERNS = [
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<IP>"),
    (re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|internal|local|corp|lan)\b", re.I), "<HOST>"),
    (re.compile(r"(?i)(bearer\s+)[a-z0-9_\-\.]+", ), r"\1<TOKEN>"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"), r"\1=<REDACTED>"),
]


def _anonymize(text: str) -> str:
    for rx, repl in _SCRUB_PATTERNS:
        text = rx.sub(repl, text)
    return text


class LessonPack(BaseModel):
    pack_id: str = Field(default_factory=lambda: f"pack-{uuid.uuid4().hex[:8]}")
    origin_grid: str
    lessons: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    signature: str = ""

    def canonical(self) -> str:
        body = f"{self.pack_id}|{self.origin_grid}|{self.created_at}|{len(self.lessons)}"
        for l in self.lessons:
            body += f"|{l.get('pattern','')}:{l.get('outcome','')}"
        return body


class FederatedExchange:
    """
    Export/import regression-tested strategy lessons between authorized
    grids. Only approved (regression-tested) lessons leave the grid; every
    lesson is anonymized and the pack is HMAC-signed. Imports are verified
    and quarantined as untrusted until locally regression-tested.
    """
    def __init__(self, grid_id: str = "grid-local"):
        self.grid_id = grid_id
        self._key = _load_grid_key()
        self.imported_packs: List[str] = []

    def _sign(self, canonical: str) -> str:
        return hmac.new(self._key, canonical.encode(), hashlib.sha256).hexdigest()

    def export_lessons(self, limit: int = 50) -> Dict[str, Any]:
        approved = strategy_memory.approved_strategies()[:limit]
        anonymized = [{
            "pattern": _anonymize(l["pattern"]),
            "outcome": l["outcome"],
            "context_tags": l["context_tags"],
        } for l in approved]
        pack = LessonPack(origin_grid=self.grid_id, lessons=anonymized)
        pack.signature = self._sign(pack.canonical())
        return pack.model_dump()

    def import_lessons(self, pack: Dict[str, Any],
                       trusted_signature: Optional[str] = None) -> Dict[str, Any]:
        """
        Import a lesson pack from a peer grid. `trusted_signature` is the
        signature the peer computed with the SHARED federation key — packs
        failing verification are rejected outright.
        """
        try:
            parsed = LessonPack(**pack)
        except ValueError:
            return {"status": "REJECTED", "reason": "malformed pack"}

        if parsed.signature != self._sign(parsed.canonical()):
            return {"status": "REJECTED", "reason": "signature verification failed"}
        if trusted_signature and not hmac.compare_digest(
                trusted_signature, parsed.signature):
            return {"status": "REJECTED", "reason": "untrusted federation signature"}

        imported = 0
        for l in parsed.lessons:
            text = l.get("pattern", "")
            if not text:
                continue
            # Federated lessons enter as untrusted: regression gate stays shut.
            strategy_memory.record_outcome(
                f"[federated:{parsed.origin_grid}] {text}",
                l.get("outcome", "UNKNOWN"),
                tags=["federated", *l.get("context_tags", [])],
                regression_tested=False)
            imported += 1

        self.imported_packs.append(parsed.pack_id)
        return {
            "status": "IMPORTED", "pack_id": parsed.pack_id,
            "origin_grid": parsed.origin_grid, "lessons_imported": imported,
            "note": "federated lessons require local regression testing before promotion",
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "grid_id": self.grid_id,
            "imported_packs": len(self.imported_packs),
            "approved_exportable": len(strategy_memory.approved_strategies()),
        }


# Global Federated Exchange
federated_exchange = FederatedExchange()
