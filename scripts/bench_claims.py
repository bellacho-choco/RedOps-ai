#!/usr/bin/env python3
"""PLAN Step 2: measure README performance claims, write benchmarks/claims.json."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def percentile(vals, p):
    vals = sorted(vals)
    k = max(0, min(len(vals) - 1, int(p / 100 * len(vals))))
    return vals[k]


def bench_bfs(iterations=1000):
    from backend.cypher_engine import graph_engine
    nodes = [f"n{i}" for i in range(200)]
    for n in nodes:
        graph_engine.add_node(n, ["host"], {})
    for i in range(len(nodes) - 1):
        graph_engine.add_edge(nodes[i], nodes[i + 1], "connects", {})
    lat = []
    for _ in range(iterations):
        t = time.perf_counter_ns()
        graph_engine.find_shortest_path(nodes[0], nodes[-1])
        lat.append((time.perf_counter_ns() - t) / 1000)
    return {"p50_us": round(percentile(lat, 50), 2),
            "p99_us": round(percentile(lat, 99), 2),
            "iterations": iterations}


def bench_ipc(iterations=1000):
    import asyncio
    from backend.swarm_bus import swarm_bus, AgentMessage

    async def run():
        lat = []
        q = swarm_bus.subscribe("bench-sink")
        for i in range(iterations):
            t = time.perf_counter_ns()
            await swarm_bus.publish(AgentMessage(
                message_id=f"bench-{i}", source_agent="bench",
                target_agent="bench-sink", event_type="bench",
                content=str(i), payload={"i": i}))
            lat.append((time.perf_counter_ns() - t) / 1000)
        return lat

    lat = asyncio.run(run())
    return {"p50_us": round(percentile(lat, 50), 2),
            "p99_us": round(percentile(lat, 99), 2),
            "p50_ms": round(percentile(lat, 50) / 1000, 4),
            "iterations": iterations}


def bench_skills():
    from backend.skills_engine import skills_engine
    return {"indexed_skills": len(skills_engine.skills)}


def bench_cython(iterations=200):
    import math
    try:
        from cython_core.fast_entropy import calculate_shannon_entropy, is_cython_accelerated
        accelerated = is_cython_accelerated()
    except Exception:
        return {"cython_available": False}

    data = b"AABBAABBCCDD\x00\x01\x02\x03" * 16
    t = time.perf_counter_ns()
    for _ in range(iterations):
        calculate_shannon_entropy(data)
    cy_us = (time.perf_counter_ns() - t) / 1000 / iterations

    def py_entropy(d):
        from collections import Counter
        c = Counter(d)
        n = len(d)
        return -sum((v / n) * math.log2(v / n) for v in c.values())

    t = time.perf_counter_ns()
    for _ in range(iterations):
        py_entropy(data)
    py_us = (time.perf_counter_ns() - t) / 1000 / iterations
    return {"cython_available": True, "accelerated": accelerated,
            "per_call_us": round(cy_us, 2), "pure_python_us": round(py_us, 2),
            "speedup": round(py_us / max(0.01, cy_us), 2)}


def main():
    claims = {
        "generated_at": time.time(),
        "cypher_bfs": bench_bfs(),
        "swarm_bus_ipc": bench_ipc(),
        "skills": bench_skills(),
        "cython_entropy": bench_cython(),
    }
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "benchmarks", "claims.json")
    with open(out, "w") as f:
        json.dump(claims, f, indent=2)
    print(json.dumps(claims, indent=2))


if __name__ == "__main__":
    main()
