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
from backend.payload_corpus import payload_corpus

REFLECTION_PROBES = ["r3d0ps{{7*7}}", "'<r3d0ps>", "r3d0ps'\"<>"]
ERROR_PROBES = ["'", "\"", "1'", "%27"]
IDOR_PROBES = ["1", "2", "0", "999999"]

# Blind-injection detection thresholds
TIME_SQLI_DELAY_S = 1.5   # baseline must be well under this
TIME_SQLI_CONFIRM_S = 1.8  # injected response slower than this => signal


def _ssti_confirmed(body: str) -> bool:
    """SSTI template markers evaluated by the server (7*7 -> 49)."""
    return ("49" in body and "{{7*7}}" not in body and "7*7" not in body)


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
                # Skill-driven corpora (falls back to builtin corpora)
                for pv in payload_corpus.payloads_for("xss-reflected", 3) or REFLECTION_PROBES:
                    await probe({param: pv}, pv)
                for pv in payload_corpus.payloads_for("sqli-error", 3) or ERROR_PROBES:
                    await probe({param: pv}, pv)
                for pv in payload_corpus.payloads_for("ssti", 2):
                    if budget["n"] <= 0:
                        break
                    budget["n"] -= 1
                    rec = await request_forge.send(endpoint.url, method=endpoint.method,
                                                   identity=identity, params={param: pv})
                    result.requests_sent += 1
                    if _ssti_confirmed(rec.body):
                        result.signals.append(Signal(
                            kind="SSTI", url=rec.url,
                            detail=f"Template expression evaluated by server: {pv!r}",
                            confidence=0.9, severity="HIGH",
                            context={"param": param, "probe": pv}))
                for pv in payload_corpus.payloads_for("idor", 3) or IDOR_PROBES:
                    await probe({param: pv}, pv)
                if budget["n"] > 1:
                    result.signals.extend(
                        await self._blind_time_probe(endpoint, param, identity, budget, result))
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

    async def _blind_time_probe(self, endpoint: Endpoint, param: str, identity: str,
                                budget: Dict[str, int], result: "FuzzResult") -> List[Signal]:
        """Time-based blind SQLi: compare baseline latency vs SLEEP-injected latency."""
        signals: List[Signal] = []
        if budget["n"] < 2:
            return signals
        budget["n"] -= 1
        base = await request_forge.send(endpoint.url, method=endpoint.method,
                                        identity=identity, params={param: "1"})
        result.requests_sent += 1
        if base.elapsed_ms >= TIME_SQLI_DELAY_S * 1000:
            return signals  # target too slow for reliable timing
        for pv in payload_corpus.payloads_for("sqli-blind-time", 2):
            if budget["n"] <= 0:
                break
            budget["n"] -= 1
            rec = await request_forge.send(endpoint.url, method=endpoint.method,
                                           identity=identity, params={param: pv})
            result.requests_sent += 1
            delta = rec.elapsed_ms - base.elapsed_ms
            if delta >= TIME_SQLI_CONFIRM_S * 1000:
                signals.append(Signal(
                    kind="BLIND_TIME_SQLI", url=rec.url,
                    detail=(f"Time-based delay confirmed: baseline {base.elapsed_ms:.0f}ms "
                            f"vs injected {rec.elapsed_ms:.0f}ms (delta {delta:.0f}ms)"),
                    confidence=0.9, severity="CRITICAL",
                    context={"param": param, "probe": pv,
                             "baseline_ms": base.elapsed_ms, "injected_ms": rec.elapsed_ms}))
                break
        return signals


fuzz_engine = FuzzEngine()
