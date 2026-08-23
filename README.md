# ⚡ REDOPS-AI: Autonomous Multi-Agent RedOps Platform

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Cypher](https://img.shields.io/badge/Cypher-Graph%20Engine-green.svg)](https://neo4j.com)
[![Cython](https://img.shields.io/badge/Cython-C--Speed%20Acceleration-yellow.svg)](https://cython.org)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**REDOPS-AI** is a multi-agent cognitive cyber-range and red-teaming architecture platform built from scratch. It features 6 specialized agent heroes operating across dedicated split-screen terminals with sub-millisecond IPC communication, an in-memory Cypher attack graph solver, Cython C-speed entropy mutation, 315+ indexed security skills, and full Docker containerization.

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
   - Ultra-low latency asynchronous message bus with Go micro-daemon channel (`< 0.1ms` packet dispatch).
3. **In-Memory Cypher Graph Engine**:
   - Real-time BFS shortest path attack graph traversal (`23.2μs` response time).
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

**OMEGA REST APIs** (server `3.0.0-OMEGA`):
`/api/mission/launch|state|abort`, `/api/gateway/token|execute|audit`,
`/api/policy/evaluate|approvals|approve|reject`, `/api/attack-paths`,
`/api/simulate/counterfactual`, `/api/evidence/finding|attach|contradict|state`,
`/api/memory/stats|outcome|lessons`

**Engine tests:**
```bash
python -m pytest tests/test_omega_engines.py -v   # 13 integration tests
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
