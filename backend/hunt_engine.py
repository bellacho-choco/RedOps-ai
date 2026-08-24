"""Autonomous Hunt Engine — chain map → fuzz → validate without human clicks.

One call runs the full kill chain against a mapped target:
  1. API Mapper discovers endpoints (real sources)
  2. Fuzz Engine probes each endpoint with skill-driven corpora
  3. Exploit Validator reproduces every signal deterministically
  4. Validated findings land in the Evidence Engine

The loop is RoE-bounded (endpoint cap, per-endpoint request budget, total
request ceiling) and reports honest zeros — a clean target yields zero
findings, not fabricated ones.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.api_mapper import api_mapper, Endpoint
from backend.fuzz_engine import fuzz_engine
from backend.exploit_validator import exploit_validator, ValidationResult
from backend.payload_corpus import payload_corpus


@dataclass
class HuntReport:
    target: str
    endpoints_mapped: int = 0
    endpoints_fuzzed: int = 0
    requests_sent: int = 0
    signals_found: int = 0
    findings_validated: int = 0
    findings_rejected: int = 0
    validations: List[Dict[str, Any]] = field(default_factory=list)
    corpus_coverage: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0


class HuntEngine:
    def __init__(self):
        self.reports: List[HuntReport] = []

    async def hunt(self, base_url: str, identity: str = "unauth",
                   max_endpoints: int = 25, max_requests_per_endpoint: int = 8,
                   total_request_ceiling: int = 150) -> HuntReport:
        t0 = time.perf_counter()
        report = HuntReport(target=base_url)

        # Phase 1: map the real attack surface
        endpoints = await api_mapper.map_target(base_url, identity=identity,
                                                max_endpoints=max_endpoints)
        report.endpoints_mapped = len(endpoints)

        # Phase 2: fuzz each endpoint; Phase 3: validate every signal
        for ep in endpoints:
            if report.requests_sent >= total_request_ceiling:
                break
            budget = min(max_requests_per_endpoint,
                         total_request_ceiling - report.requests_sent)
            if budget <= 0:
                break
            result = await fuzz_engine.fuzz_endpoint(
                ep, identity=identity, max_requests=budget)
            report.endpoints_fuzzed += 1
            report.requests_sent += result.requests_sent

            for signal in result.signals:
                report.signals_found += 1
                param = (signal.context or {}).get("param")
                params = {param: signal.context["probe"]} if param and "probe" in (signal.context or {}) else None
                validation: ValidationResult = await exploit_validator.validate(
                    signal, method=ep.method, identity=identity, params=params)
                report.requests_sent += exploit_validator.REPRODUCTIONS_REQUIRED
                if validation.validated:
                    report.findings_validated += 1
                else:
                    report.findings_rejected += 1
                report.validations.append({
                    "kind": validation.signal_kind, "url": validation.url,
                    "validated": validation.validated,
                    "confidence": validation.confidence,
                    "finding_id": validation.finding_id})

        report.corpus_coverage = payload_corpus.coverage_report()
        report.elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        self.reports.append(report)
        return report

    def latest(self) -> Optional[HuntReport]:
        return self.reports[-1] if self.reports else None


hunt_engine = HuntEngine()
