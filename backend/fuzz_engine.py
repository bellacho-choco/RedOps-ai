"""Fuzzing Engine — real payload probes against discovered endpoints.

Sends real requests (via governed RequestForge) with mutation payloads,
collects ResponseRecords, and hands everything to the ResponseAnalyzer.
Coverage and request counts are tracked so runs are reproducible and
RoE-bounded. Payload corpora are conservative: error/reflection-detection
probes only — no destructive or DoS payloads.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.api_mapper import Endpoint
from backend.request_forge import request_forge
from backend.response_analyzer import response_analyzer, Signal

REFLECTION_PROBES = ["r3d0ps{{7*7}}", "'<r3d0ps>", "r3d0ps'\"<>"]
ERROR_PROBES = ["'", "\"", "1'", "%27"]
IDOR_PROBES = ["1", "2", "0", "999999"]


@dataclass
class FuzzResult:
    url: str
    requests_sent: int = 0
    signals: List[Signal] = field(default_factory=list)
    elapsed_ms: float = 0.0


class FuzzEngine:
    def __init__(self):
        self.history: List[FuzzResult] = []

    async def fuzz_endpoint(self, endpoint: Endpoint, identity: str = "unauth",
                            max_requests: int = 12) -> FuzzResult:
        t0 = time.perf_counter()
        result = FuzzResult(url=endpoint.url)
        budget = {"n": max_requests}

        async def probe(params: Dict[str, Any], probe_value: str):
            if budget["n"] <= 0:
                return
            budget["n"] -= 1
            rec = await request_forge.send(endpoint.url, method=endpoint.method,
                                           identity=identity, params=params)
            result.requests_sent += 1
            result.signals.extend(response_analyzer.analyze(rec, probe=probe_value))

        if not endpoint.params:
            rec = await request_forge.send(endpoint.url, method=endpoint.method,
                                           identity=identity)
            result.requests_sent += 1
            result.signals.extend(response_analyzer.analyze(rec))
        else:
            for param in endpoint.params[:3]:
                if param.startswith("graphql:"):
                    continue
                for pv in REFLECTION_PROBES:
                    await probe({param: pv}, pv)
                for pv in ERROR_PROBES:
                    await probe({param: pv}, pv)
                for pv in IDOR_PROBES:
                    await probe({param: pv}, pv)
                if budget["n"] <= 0:
                    break

        # dedupe signals
        seen, unique = set(), []
        for s in result.signals:
            key = (s.kind, s.detail[:80])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        result.signals = unique
        result.elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        self.history.append(result)
        return result

    async def idor_check(self, url: str, identity_a: str, identity_b: str) -> List[Signal]:
        """Same resource fetched under two identities; B≈A means IDOR signal."""
        rec_a = await request_forge.send(url, identity=identity_a)
        rec_b = await request_forge.send(url, identity=identity_b)
        return response_analyzer.compare_identities(rec_a, rec_b)


fuzz_engine = FuzzEngine()
