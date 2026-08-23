#!/usr/bin/env python3
"""
REDOPS-Ω flagship demo: one command runs the entire cognitive pipeline
against a local, authorized scope (default 127.0.0.1 — zero collateral).

Usage: python scripts/omega_demo.py [target]
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")

from backend.omega_runner import omega_runner  # noqa: E402


async def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    print(f"⚡ REDOPS-Ω PIPELINE — target: {target}\n")
    report = await omega_runner.run(target)

    for s in report.stages:
        icon = {"OK": "✅", "WARN": "⚠️ ", "FAILED": "❌"}.get(s.status, "•")
        print(f"  {icon} {s.stage:26} {s.status:7} {s.elapsed_ms:>8.2f} ms")

    cert = report.scorecard.get("trust_certificate", {})
    gsi = report.scorecard.get("gsi", {})
    bench = report.scorecard.get("benchmark", {})
    print(f"""
══════════════════════════════════════════════
  Mission       : {report.mission_status}
  Witness valid : {report.witness_valid}
  GSI grade     : {gsi.get('grade')} (score {gsi.get('score')})
  Benchmark     : {bench.get('grade')} | publishable={bench.get('publishable')}
  Trust cert    : {cert.get('certificate_id')} valid={cert.get('valid')}
  Report        : {report.report_path}
══════════════════════════════════════════════""")
    failed = [s for s in report.stages if s.status == "FAILED"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
