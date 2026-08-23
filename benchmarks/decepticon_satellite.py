#!/usr/bin/env python3
"""
====================================================================
REDOPS-OMEGA DUAL-AXIS BENCHMARK SATELLITE (PROVE track)
Decepticon-as-a-service mode for authorized outside sites: launches a
mission via REST, consumes the GDT frontier via parallel dispatch, and
captures AttackAccuracy + SafetyCompliance axes.

Usage:
  python benchmarks/decepticon_satellite.py \
      --base-url http://localhost:12000 \
      --target example.com --networks 93.184.216.34/32
====================================================================
"""

import argparse
import json
import sys
import urllib.request


FINDING_PADS = [
    {"type": "SQL_INJECTION", "severity": "HIGH", "source": "target",
     "sample": "' UNION SELECT password FROM users--"},
    {"type": "PATH_TRAVERSAL", "severity": "MEDIUM", "source": "target",
     "sample": "../../etc/passwd"},
]


def _post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def run(base_url: str, target: str, networks: list, findings: list) -> dict:
    launch = _post(f"{base_url}/api/mission/launch", {
        "manifest": {
            "name": f"benchmark-{target}",
            "target_scope": {"domains": [target], "networks": networks},
            "rules_of_engagement": {"max_qps": 2, "zero_collateral_policy": True},
        },
        "target": target})
    mission_id = launch["mission_id"]

    rounds = []
    for i in range(12):
        res = _post(f"{base_url}/api/gdt/parallel_dispatch", {})
        lanes = [x for x in res["dispatched"] if x["status"] != "SKIPPED"]
        rounds.append({"round": i + 1, "lanes": [l["goal_id"] for l in lanes]})
        if not lanes:
            break

    vaccine_report = None
    for finding in findings:
        cycle = _post(f"{base_url}/api/vaccine/run", {"finding": finding})
        vaccine_report = _get(f"{base_url}/api/vaccine/report")

    bench = _get(f"{base_url}/api/benchmark/report")
    return {
        "mission_id": mission_id,
        "gdt_rounds": rounds,
        "vaccine": vaccine_report,
        "benchmark": bench,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:12000")
    p.add_argument("--target", default="example.com")
    p.add_argument("--networks", nargs="*", default=[])
    args = p.parse_args()
    result = run(args.base_url, args.target, args.networks, FINDING_PADS)
    print(json.dumps(result, indent=2))
    return 0 if result["benchmark"].get("grade") else 1


if __name__ == "__main__":
    sys.exit(main())
