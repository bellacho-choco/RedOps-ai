# ⚡ REDOPS-AI: Autonomous Multi-Agent RedOps Platform

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Cypher](https://img.shields.io/badge/Cypher-Graph%20Engine-green.svg)](https://neo4j.com)
[![Cython](https://img.shields.io/badge/Cython-C--Speed%20Acceleration-yellow.svg)](https://cython.org)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**REDOPS-AI** is a multi-agent cognitive cyber-range and red-teaming architecture platform built from scratch. It features 6 specialized agent heroes operating across dedicated split-screen terminals with sub-millisecond IPC communication, an in-memory Cypher attack graph solver (~177μs BFS p50 on a 200-node graph, measured), Cython entropy mutation with pure-Python fallback, 315+ indexed security skills (317 measured), and full Docker containerization.

---

## 🌟 Architecture & 6 Hero Agents

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                             REDOPS-AI SWARM MATRIX                                │
├──────────────────────────┬──────────────────────────┬─────────────────────────────┤
│ 👑 OVERLORD-PRIME        │ 🛰️ SPECTRE-RECON         │ 🧬 NEXUS-CYPHER             │
│ • Role: Commander        │ • Role: Surface Hunter   │ • Role: Graph Engine        │
│ • 24 Planning Skills     │ • 58 Recon/OSINT Skills  │ • 14 Graph/AD Skills        │
├──────────────────────────┼──────────────────────────┼─────────────────────────────┤
│ ⚡ VORTEX-EXPLOIT        │ 🛡️ CIPHER-MORPH          │ 📊 CHRONO-DEBRIEF           │
│ • Role: Vuln Synthesizer │ • Role: Evasion Core     │ • Role: Intel Architect     │
│ • 166 Exploit/MPC Skills │ • 51 Reversing/C2 Skills │ • 2+ Defense Playbooks      │
└──────────────────────────┴──────────────────────────┴─────────────────────────────┘
```

---

## 🚀 Key Features

1. **Dedicated Multi-Terminal Cockpits**:
   - Interactive Rich-powered **Fullscreen Split-Terminal TUI** (`python run.py --mode tui`).
   - Interactive **Command Line REPL** (`python run.py --mode cli`).
   - Futuristic **Web Cockpit HUD** with interactive Canvas attack graph visualizer (`http://127.0.0.1:8000`).
2. **Sub-Millisecond Inter-Agent IPC**:
   - Ultra-low latency asynchronous message bus with Go micro-daemon channel (measured: ~4μs p50 dispatch — see `benchmarks/claims.json`).
3. **In-Memory Cypher Graph Engine**:
   - Real-time BFS shortest path attack graph traversal (measured: 177μs p50 on a 200-node graph — see `benchmarks/claims.json`).
4. **Cython Hardware Acceleration**:
   - C-speed Shannon entropy math and polymorphic bytecode mutation modeling.
5. **315+ Indexed Security Skills**:
   - Full discovery engine indexing categories like Active Directory, Cloud, Wireless, MPC Cryptography, AST Taint analysis, Reverse Engineering, C2, and DFIR.
6. **Full Docker Containerization**:
   - Multi-stage `Dockerfile` and `docker-compose.yml` for 1-click deployment.

---

## Ω REDOPS-OMEGA Layer (Phase I Implemented)

Six new governed engines now sit between the swarm and the outside world
(see `REDOPS_OMEGA_BLUEPRINT.md` for the full specification):

| Engine | File | Capability |
| :--- | :--- | :--- |
| **Mission & Goal System** | `backend/mission_engine.py` | Mission Manifests, Goal Dependency Trees (DAG), cycle detection, 3-strike circuit breaker |
| **Policy & Authorization** | `backend/policy_engine.py` | Hazardous payload classification, MITRE high-impact gates, HMAC capability tokens, human approval tickets |
| **Tool Gateway** | `backend/tool_gateway.py` | Post-DNS scope enforcement, RoE QPS/hour limits, hash-chained tamper-evident audit ledger |
| **Attack-Path Engine** | `backend/attack_path_engine.py` | Kill-chain enumeration + Path Scoring (Likelihood × Exploitability × Privilege Gain × Criticality × Blast Radius) + Counterfactual IF→THEN simulator |
| **Evidence & Validation** | `backend/evidence_engine.py` | SHA-256 evidence tokens, confidence scoring, false-positive downgrade, auto repro scripts |
| **Strategy Memory** | `backend/strategy_memory.py` | 3-tier memory: session deque, campaign KV, regression-gated long-term lessons |
| **AI-vs-AI Defense** | `backend/defense_engine.py` | Blue-team sigma-style ruleset + Shannon-entropy anomaly inspection; red-vs-blue simulation campaigns with mutation escalation, blind-spot flagging & remediation synthesis |
| **Benchmarking** | `backend/benchmark_engine.py` | Continuous evaluation: attack / accuracy / safety metric families + composite S–D grade + trend history |
| **Sandbox Labs** | `backend/sandbox_engine.py` | 3-tier non-destructive validation: container exploit dry-runs, virtualized AD chain rehearsal on the World Model, browser client-payload static evaluation + distributed grid registry |
| **GDT Orchestration** | `backend/agents.py` | OVERLORD-PRIME executes missions as Goal Dependency Trees — every goal under circuit breaker, every scan routed through the governed Tool Gateway |
| **Vector Memory** (Phase II) | `backend/vector_memory.py` | Deterministic token+bigram+trigram embeddings, cosine semantic recall, atomic disk persistence — lessons survive restarts and are found by meaning |
| **Mission Persistence** (Phase II) | `backend/mission_engine.py` | Snapshot/restore of manifests + GDT states; restored ACTIVE missions downgrade to INTERRUPTED (never silently resume) |
| **Self-Healing** (Phase III) | `backend/self_healing_engine.py` | SAST findings → synthesized patch drafts (parameterized SQL, eval dispatch, env-sourced secrets) → evidence anchoring → regression-gated lessons |
| **Federated Exchange** (Phase III) | `backend/federated_exchange.py` | Cross-grid lesson sharing: IP/host/credential anonymization + HMAC-signed packs; imports verified & quarantined until local regression |
| **Cognition Daemon** (Phase IV) | `backend/cognition_daemon.py` | Continuous adversarial reasoning loop: World-Model fingerprint drift detection, counterfactual forecasting, finding revalidation, OBSERVE/REASSESS/ALERT directives |

### Satellite-Beating Extensions (BEAT track)

| Capability | Module | Description |
|---|---|---|
| **Offensive Vaccine Loop** (flagship) | `backend/vaccine_engine.py` | Closed loop: finding → rule synthesis → guided mutation replay → IMMUNIZED/BLIND_SPOT verdict → patch draft + regression-gated lesson |
| **Live Threat Research** (flagship) | `backend/intel_engine.py` | Tavily HTTP connector w/ TTL cache; degrades gracefully to NO_KEY |
| **Hybrid World Model** | `backend/cypher_engine.py` | Write-through JSONL journal + replay restore + optional NEO4J_URI write-behind replica |
| **Real Container Sandbox** | `backend/sandbox_engine.py` | DockerExecutor: ephemeral Kali runs + tmux-style sessions, prompt detection, cap_drop ALL |
| **Sonic Speed Layer** | `backend/parallel_dispatch.py` | Bounded parallel READY-goal fan-out with isolated LaneContext (fresh-context isolation) |
| **Batch Recon + Caching** | `backend/live_scanner.py` | Per-host recon streams + Cymru-style TTL cache |
| **Signed Engagement Package** | `backend/mission_engine.py` | RoE/ConOps/OPPLAN + MITRE mapping, HMAC-sealed |

**Satellite-beat APIs**:
`/api/vaccine/run|report|status/{id}`, `/api/intel/research|cache`,
`/api/sandbox/session/open|input|close`, `/api/mission/package|package/verify`,
`/api/gdt/parallel_dispatch`, `/api/recon/batch`.

### OMEGA Pipeline (Phase 4 flagship)

One command runs the whole cognitive pipeline — preflight health → governed
GDT mission → environment model → attack-path reasoning → signed witness
export → claim validation → composite scorecard with a tamper-evident
**trust certificate** over measured claims only.

- Runner: `backend/omega_runner.py` | Demo: `python scripts/omega_demo.py 127.0.0.1`
- CLI: `omega [target]` inside `run.py --mode cli`
- API: `POST /api/omega/run`, `POST /api/trust/certificate`,
  `POST /api/synthesis/skill`, `GET /api/synthesis/staged`

**Controlled self-improvement** (`backend/synthesis_engine.py`): regression-tested
strategy lessons are synthesized into SKILL.md drafts in `skills/staging/`
(PENDING_APPROVAL) — validated by the same PyYAML frontmatter parser as the
live index, never auto-promoted.

**Benchmark rigor** (`backend/benchmark_engine.py`): rot-detection health
pre-checks exclude dead targets from scoring (transparent, not silent),
seeded deterministic replay, per-finding JSONL traces. Measured performance
claims are reproducible via `scripts/bench_claims.py` → `benchmarks/claims.json`.

**Skills audit**: `GET /api/skills/audit` (per-agent counts, missing
frontmatter/tags, duplicate names, parser mode), MITRE ATT&CK lookup at
`GET /api/skills/mitre/{technique_id}`.

**OMEGA REST APIs** (server `3.0.0-OMEGA`):
`/api/mission/launch|state|abort`, `/api/gateway/token|execute|audit`,
`/api/policy/evaluate|approvals|approve|reject`, `/api/attack-paths`,
`/api/simulate/counterfactual`, `/api/evidence/finding|attach|contradict|state`,
`/api/memory/stats|outcome|lessons`, `/api/defense/rules|inspect`,
`/api/simulate/ai-vs-ai`, `/api/benchmark/report|history`,
`/api/sandbox/dry-run|rehearse|client-payload|stats|grid|grid/register`,
`/api/memory/vector/recall|stats`, `/api/mission/snapshot|restore`,
`/api/heal/scan|status|stats`, `/api/federation/export|import|stats`,
`/api/cognition/start|stop|cycle|state`

**MCP Bridge** (Model Context Protocol, Section 7):
`/mcp/world-model`, `/mcp/skills`, `/mcp/skills/{name}`, `/mcp/sandbox/validate`

**Engine tests:**
```bash
python -m pytest tests/ -v   # 36 integration tests (all phases I–IV)
```

---

## 🐳 Quick Start with Docker

```bash
# Start Web Cockpit & Daemon in background
docker compose up --build -d

# Open Web UI
http://127.0.0.1:8000

# Run interactive TUI inside Docker
docker compose run --rm redops-cli
```

---

## 💻 Local Setup & Execution

### Prerequisites
- Python 3.10+
- Optional: Go 1.22+, GCC/Clang (for Cython compilation)

### Installation
```bash
git clone https://github.com/bellacho-choco/RedOps-ai.git
cd RedOps-ai
pip install fastapi uvicorn websockets pydantic rich prompt_toolkit httpx dnspython
```

### Running Modes

#### 1. Interactive Command Line REPL
```bash
python run.py --mode cli
```
*Useful commands inside REPL:*
- `swarm start` — Deploys all 6 hero agents in autonomous kill-chain emulation.
- `skills` — Displays the 315+ skills distribution across agents.
- `skills <keyword>` — Searches for specific skills (e.g. `skills mpc`, `skills wireless`, `skills sqli`).
- `skill-read <name>` — Renders the complete playbook directly in terminal.
- `cypher <query>` — Executes instant graph pathfinding queries.
- `tui` — Switches into fullscreen split cockpit.

#### 2. Fullscreen Split-Terminal Cockpit (TUI)
```bash
python run.py --mode tui
```

#### 3. Web Command Center HUD
```bash
python run.py --mode web
```

---

## 📁 Repository Structure

```
RedOps-ai/
├── backend/
│   ├── agents.py           # 6 Specialized Agent Heroes Matrix
│   ├── cypher_engine.py    # In-memory Cypher Graph Database & Solver
│   ├── skills_engine.py    # Dynamic 315+ Skills Indexer & Bridge
│   ├── swarm_bus.py        # Sub-millisecond Async IPC Message Bus
│   └── server.py           # FastAPI WebSockets & REST API Server
├── cli/
│   ├── interactive_cli.py  # Interactive CLI REPL
│   └── terminal_matrix.py  # Rich-powered 6-Agent Split Terminal HUD
├── cypher/                 # Cypher graph schemas & queries
├── cython_core/            # Cython C-speed acceleration & fallback
├── frontend/               # TypeScript interfaces & source definitions
├── go_daemon/              # Go low-latency packet micro-daemon
├── scripts/                # 1-click startup automation (PowerShell/Bash)
├── skills/                 # 315+ Security skill playbooks & taxonomy
├── static/                 # Web Cockpit HUD (Canvas visualizer & synth)
├── Dockerfile              # Multi-language container build
├── docker-compose.yml      # Service orchestration
└── run.py                  # Root CLI launcher
```

---

## 📜 License
MIT License.

## NEXT-PHASE SATELLITES

- /api/plugins governed marketplace (publish/install/trust gating)
- /api/gsi/score composite global security index (0-100)
- /api/wizard/preflight go/no-go preflight for sandbox/intel/audit ledger

## EVOLUTION ENGINE (SELF-IMPROVEMENT)

- `/api/evolution/cycle` posture -> weak axis -> vaccine cycles -> lessons -> re-score (ADVANCE/HOLD/REGRESS)
- `/api/evolution/report` loop history + GSI trend
