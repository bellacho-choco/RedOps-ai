"""
====================================================================
PROJECT REDOPS-OMEGA - VECTOR MEMORY ENGINE (PHASE II: 2030)
Embedding-based semantic recall for long-term strategy memory with
disk persistence. Uses deterministic token-hashing embeddings (no
external model dependency) + cosine similarity. Blueprint Section 5,
Tier 3 upgrade + Section 15 Phase II.
====================================================================
"""

import hashlib
import json
import math
import os
import re
import time
import uuid
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

EMBEDDING_DIM = 512
DEFAULT_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".redops_memory", "vector_store.json")

_TOKEN_RE = re.compile(r"[a-z0-9_\-\.]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def embed_text(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Deterministic embedding: each token (and token bigram) is hashed into
    the vector space with a signed weight, then L2-normalized. Captures
    lexical semantics well enough for strategy-lesson recall without
    shipping a transformer.
    """
    vec = [0.0] * dim
    tokens = _tokenize(text)
    # Exact tokens carry the strongest signal; bigrams and character
    # trigrams add contextual + subword fuzziness ("tunnel" ~ "tunneling").
    feats = [(t, 3.0) for t in tokens]
    feats += [(f"{a}~{b}", 2.0) for a, b in zip(tokens, tokens[1:])]
    for tok in tokens:
        padded = f"#{tok}#"
        feats += [(padded[i:i + 3], 1.0) for i in range(len(padded) - 2)]
    for feat, boost in feats:
        digest = hashlib.sha256(feat.encode()).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = boost * (1.0 + (digest[5] / 255.0))
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    return round(sum(x * y for x, y in zip(a, b)), 4)


class VectorEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: f"vec-{uuid.uuid4().hex[:8]}")
    text: str
    embedding: List[float] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    outcome: str = "UNKNOWN"
    created_at: float = Field(default_factory=time.time)


class VectorMemoryEngine:
    """
    Semantic long-term store. Lessons indexed by embedding can be recalled
    by *meaning* (e.g. 'waf bypass attempt' recalls 'modsecurity evasion
    failure') rather than exact signature match. Persists to disk so
    campaign knowledge survives restarts (Phase II persistence milestone).
    """
    def __init__(self, store_path: str = DEFAULT_STORE_PATH):
        self.store_path = store_path
        self.entries: Dict[str, VectorEntry] = {}
        self._load()

    # ---------------------------------------------------------------
    def index_lesson(self, text: str, outcome: str,
                     metadata: Optional[Dict[str, Any]] = None) -> VectorEntry:
        entry = VectorEntry(
            text=text[:500], embedding=embed_text(text),
            outcome=outcome.upper(), metadata=metadata or {},
        )
        self.entries[entry.entry_id] = entry
        self._persist()
        return entry

    def recall_similar(self, query: str, limit: int = 5,
                       min_score: float = 0.1) -> List[Dict[str, Any]]:
        q_vec = embed_text(query)
        scored = [
            (cosine_similarity(q_vec, e.embedding), e)
            for e in self.entries.values()
        ]
        scored = [(s, e) for s, e in scored if s >= min_score]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{
            "entry_id": e.entry_id, "text": e.text, "outcome": e.outcome,
            "similarity": s, "metadata": e.metadata, "created_at": e.created_at,
        } for s, e in scored[:limit]]

    def forget_stale(self, older_than_days: float = 90) -> int:
        cutoff = time.time() - older_than_days * 86400
        stale = [k for k, e in self.entries.items() if e.created_at < cutoff]
        for k in stale:
            del self.entries[k]
        if stale:
            self._persist()
        return len(stale)

    def get_stats(self) -> Dict[str, Any]:
        outcomes: Dict[str, int] = {}
        for e in self.entries.values():
            outcomes[e.outcome] = outcomes.get(e.outcome, 0) + 1
        return {
            "entries_total": len(self.entries),
            "by_outcome": outcomes,
            "embedding_dim": EMBEDDING_DIM,
            "store_path": self.store_path,
            "persisted": os.path.exists(self.store_path),
        }

    # ---------------------------------------------------------------
    def _persist(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        payload = [e.model_dump() for e in self.entries.values()]
        tmp = self.store_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, self.store_path)  # atomic swap; no torn writes

    def _load(self):
        if not os.path.exists(self.store_path):
            return
        try:
            with open(self.store_path) as fh:
                for raw in json.load(fh):
                    entry = VectorEntry(**raw)
                    self.entries[entry.entry_id] = entry
        except (json.JSONDecodeError, ValueError):
            pass  # corrupt store -> start clean, never crash the swarm


# Global Vector Memory
vector_memory = VectorMemoryEngine()
