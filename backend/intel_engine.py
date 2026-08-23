"""
====================================================================
PROJECT REDOPS-OMEGA - LIVE THREAT RESEARCH ENGINE (BEAT #2, FLAGSHIP)
Decepticon lists 'connectors' on the roadmap. We ship a governed live
research connector (Tavily HTTP) with TTL cache + graceful degrade.

Fixes the champion gap '17B untrained': the agent now reasons over the
fresh exploit landscape, not only over its frozen baseline.
====================================================================
"""

import hashlib
import os
import time
from typing import Dict, List, Any, Optional

import httpx
from pydantic import BaseModel, Field


CACHE_TTL_S = 300  # 5min freshness window


class ThreatIntelItem(BaseModel):
    title: str
    url: str
    relevance: float = 0.0
    snippet: str = ""


class ThreatIntelReport(BaseModel):
    query: str
    status: str = "OK"            # OK | NO_KEY | UPSTREAM_ERROR | CACHED
    items: List[ThreatIntelItem] = Field(default_factory=list)
    cached: bool = False
    cache_age_s: float = 0.0
    fetched_at: float = Field(default_factory=time.time)
    upstream_latency_ms: float = 0.0


class IntelEngine:
    """Governed live threat research via Tavily HTTP, TTL-cached."""

    SEARCH_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: Optional[str] = None, ttl_s: int = CACHE_TTL_S):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.ttl_s = ttl_s
        self._cache: Dict[str, ThreatIntelReport] = {}

    # ----------------------------------------------------------------
    def research(self, query: str, depth: str = "basic",
                 max_results: int = 5) -> ThreatIntelReport:
        if not self.api_key:
            return ThreatIntelReport(query=query, status="NO_KEY")
        key = hashlib.sha256(f"{query}|{depth}".encode()).hexdigest()
        hit = self._cache.get(key)
        if hit and time.time() - hit.fetched_at < self.ttl_s:
            return hit.model_copy(update={"cached": True,
                                          "cache_age_s": round(time.time() - hit.fetched_at, 2),
                                          "status": "CACHED"})
        started = time.perf_counter()
        try:
            resp = httpx.post(
                self.SEARCH_URL,
                json={"api_key": self.api_key, "query": query,
                      "search_depth": depth, "max_results": max_results},
                timeout=8.0)
            report = ThreatIntelReport(
                query=query,
                items=[ThreatIntelItem(
                    title=r.get("title", ""), url=r.get("url", ""),
                    relevance=r.get("score", 0.0),
                    snippet=(r.get("content") or "")[:240])
                    for r in resp.json().get("results", [])],
                upstream_latency_ms=round((time.perf_counter() - started) * 1000, 2))
        except Exception as exc:
            return ThreatIntelReport(query=query, status="UPSTREAM_ERROR",
                                     items=[ThreatIntelItem(title="upstream failure",
                                                             url="", snippet=str(exc))])
        self._cache[key] = report
        return report

    def get_stats(self) -> Dict[str, Any]:
        return {"cached_queries": len(self._cache),
                "ttl_s": self.ttl_s,
                "key_configured": bool(self.api_key)}


# Global Intel Engine
intel_engine = IntelEngine()
