# AGENTS.md — REDOPS-Ω repo knowledge

Project: REDOPS-Ω — autonomous adversarial-security intelligence platform
(Python 3.13, FastAPI, in-memory Cypher-native graph).

## Key architecture
- `backend/server.py` FastAPI app wires ~18 engines; global singletons per
  module; Tool Gateway enforced (no ACTIVE mission → sealed).
- GDT: `mission_engine.py` — GoalNode states READY → RUNNING → DONE/FAILED;
  `attempts>=max_attempts → BLOCKED`.
- World model: `cypher_engine.py` (`CypherGraphEngine`) with write-through
  JSONL journal + replay + optional Neo4jSyncAdapter (NEO4J_URI gated).
- Safety: `policy_engine.py` (RBAC, capability tokens, scope check,
  approval gates), `audit_engine.py` hash-chained records.
- New BEAT modules: `vaccine_engine` (closed loop), `intel_engine` (Tavily),
  `parallel_dispatch` (isolated LaneContext), `sandbox_engine.DockerExecutor`.

## Common commands
- Tests: `python -m pytest tests/ -q` (uses asyncio.run pattern for async)
- Server: `uvicorn backend.server:app --port 12000`
- Satellite benchmark: `python benchmarks/decepticon_satellite.py --base-url ...`

## Conventions
- Style: banner docstrings (PROJECT REDOPS-OMEGA / BEAT #N), patch-style
  optional deps, from-import singletons (e.g. `from backend.X import x`).
- Branches: one feature branch per theme (e.g., `decepticon-beat`), PR
  targets `main`, user on GitHub bellacho-choco/RedOps-ai.
- Optional dependencies must degrade gracefully (docker/neo4j/tavily).

## Gotchas hit
- GoalNode defaults max_attempts=3 (assert blocked-state accordingly).
- Endpoint response shapes: launch returns `mission_id` top-level, not nested.
- `benchmarks/satellite` uses python-stdlib urllib (no extra deps).
