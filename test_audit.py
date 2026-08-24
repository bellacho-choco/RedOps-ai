import asyncio
from backend.sast_analyzer import sast_auditor
from backend.live_scanner import socket_scanner
from backend.skills_engine import skills_engine
from backend.cypher_engine import graph_engine
from backend.agents import swarm_matrix
from cython_core.fast_entropy import calculate_shannon_entropy

def test_all():
    print("[1] Testing SAST Analyzer...")
    code = 'def test():\n    exec("SELECT " + user_input)'
    findings = sast_auditor.analyze_buffer(code, "test.py")
    print(f"    -> Findings detected: {len(findings)}")

    print("[2] Testing Skills Engine...")
    summary = skills_engine.get_summary()
    print(f"    -> Total Skills indexed: {summary['total_skills']}")

    print("[3] Testing Cypher Graph Engine...")
    q = "MATCH (start:Host {zone: 'DMZ'}), (target:Host {zone: 'CORE_MATRIX'}) MATCH p = shortestPath((start)-[*]->(target)) RETURN p"
    res = graph_engine.execute_query(q)
    print(f"    -> Cypher Query Time: {res.get('execution_time_us')}us | Status: {res.get('status')}")

    print("[4] Testing Shannon Entropy...")
    ent = calculate_shannon_entropy(b"RedOps-AI High Speed Entropy Test")
    print(f"    -> Entropy score: {ent:.4f} bits/byte")

    print("[5] Testing Swarm Matrix Agents...")
    print(f"    -> Loaded Agents: {list(swarm_matrix.agents.keys())}")

if __name__ == "__main__":
    test_all()
