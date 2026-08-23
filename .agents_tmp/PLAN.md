# 1. OBJECTIVE

RedOps-ai ko Decepticon ko **beat** karke banana — sirf gaps close nahi, balki leapfrog. Decepticon ki har strength ka governed-superior version ship karna, PLUS wo flagship features jo Decepticon mein exist hi nahi karte — sabse bade: **(1) Offensive Vaccine loop jo Decepticon ne sirf PLAN kiya hai, hum SHIP karenge**, aur **(2) Tavily-powered LIVE Threat Research Engine** — real-time hacking-technique/CVE/exploit research jo Decepticon ke agents ke paas nahi hai (woh sirf static model knowledge par chalte hain). Saath mein **Sonic-speed execution layer** — parallel GDT, Cython fast-paths, sub-second recon. End state: "Decepticon jaisa real execution, lekin cryptographically governed, live-research-driven, blazing-fast, self-learning, aur defense-closing — jo koi aur platform nahi deta."

# 2. CONTEXT SUMMARY

**Decepticon Beat-Matrix (parity gaps + leapfrog opportunities):**

| Area | Decepticon (4.9k⭐) | RedOps-ai | Beat Strategy |
| :--- | :--- | :--- | :--- |
| Tool Execution | REAL: Kali sandbox, tmux sessions | Simulated dry-runs + `live_scanner.py` | PARITY++: real Docker exec, lekin har command HMAC-gated + hash-chained audited (Decepticon mein nahi) |
| Sandbox | Two-network isolation (`decepticon-net`/`sandbox-net`) | Registry/simulation tiers | PARITY: `sandbox-net` compose network + real containers |
| Offensive Vaccine | **SIRF PLANNED** (docs confirm: "not an active implementation") | defense_engine + self_healing + evidence + sandbox ALL EXIST | **BEAT #1 (flagship):** closed loop ship karna — attack→defend→verify→patch→regression |
| Governance | Basic safety gate | Policy Engine, HMAC tokens, audit ledger, Evidence, circuit breakers | **BEAT #2:** governed real execution + signed engagement package |
| Graph | Neo4j persistent (network round-trips) | In-memory 23μs BFS, no persistence | **BEAT #3:** hybrid — in-memory speed + write-through persistence (dono ka best) |
| Learning | Stateless per engagement | strategy_memory + vector_memory | **BEAT #4:** self-improving evasion — failed payloads ka lesson agle mutation mein |
| Benchmarks | XBOW 102/104 (98.08%) — attack-only | Internal engine only | **BEAT #5:** dual-axis publish — attack pass-rate + safety/compliance score (industry first) |
| Agents | 16 specialists, fresh-context per objective | 6 heroes, GDT orchestration | PARITY: fresh-context-per-goal GDT nodes par |
| Threat Research | **NONE built-in** — agents sirf static LLM training knowledge use karte hain | No live intel (skills static markdown) | **BEAT #6:** Tavily-powered live research engine — latest CVEs, exploit writeups, TTPs real-time; findings World Model + vector memory mein feed |
| Speed | Sequential LangGraph objective loop | swarm_bus <0.1ms IPC (already fast) | **BEAT #7:** Sonic layer — parallel GDT branches, async batch recon, Cython fast-paths, intel cache; target: full recon+research cycle sub-60s |
| Packaging | PyPI SDK + plugin bundles | Repo only | PARITY: `pyproject.toml` + PluginBundle-style skills packaging |

**Key files:** `backend/{sandbox,tool_gateway,policy,mission,defense,self_healing,evidence,benchmark,cypher,strategy,vector}_*.py`, new `backend/vaccine_engine.py`, new `backend/intel_engine.py`, `backend/server.py`, `backend/agents.py`, `backend/live_scanner.py`, `backend/swarm_bus.py`, `docker-compose.yml`, `cython_core/fast_entropy.pyx`, new `benchmarks/`, new `pyproject.toml`, `tests/`

**Constraints:**
- Saara real execution Policy Engine + Tool Gateway se gated — koi bypass nahi (yahi differentiator hai).
- Existing 36 tests green rehne chahiye; engines ke public APIs break nahi karne.

# 3. APPROACH OVERVIEW

3 tracks mein kaam — **PARITY** (Decepticon jitna), **BEAT** (usse aage), **PROVE** (public saboot):

**Track A — PARITY (Steps 1–3):** Real governed sandbox execution + interactive sessions + engagement package. Decepticon ka core advantage (real tools) neutralize karna, lekin Day-1 se governed.

**Track B — BEAT (Steps 4–9):** Wo features jo Decepticon mein hain hi nahi:
1. **Offensive Vaccine shipped** — unka planned feature humara shipped feature (existing engines ko loop mein wire karna)
2. **Hybrid World Model** — in-memory 23μs speed + write-through persistence
3. **Self-improving evasion** — strategy/vector memory se mutation learning
4. **Tavily Live Threat Research** — real-time CVE/exploit/TTP research engine (Decepticon mein koi live intel nahi)
5. **Sonic Speed Layer** — parallel GDT execution, async batch recon, Cython fast-paths, intel caching (target: recon+research cycle sub-60s)

**Track C — PROVE (Steps 10–12):** Dual-axis public benchmark + PyPI packaging + docs — credibility aur distribution.

Order ka logic: pehle execution foundation (A), phir leapfrog features (B), phir public proof (C). Tavily engine aur speed layer Steps 1–2 ke baad aate hain kyunki agents ko governed-execution + live-intel dono chahiye.

# 4. IMPLEMENTATION STEPS

## Track A — PARITY: Real Governed Execution

**Step 1: Real Container Execution Backend**
- **Goal:** Simulated sandbox tiers ko real Docker execution se replace karna.
- **Method:** `sandbox_engine.py` mein `DockerExecutor` — docker Python SDK se ephemeral Kali containers, `docker exec`-based persistent session manager (tmux-style), stdout/stderr capture with timeouts. `docker-compose.yml` mein isolated `sandbox-net` network + `redops-sandbox` service (Kali tooling image) add karna.
- **Reference:** `backend/sandbox_engine.py`, `docker-compose.yml`

**Step 2: Governed Execution Wiring (BEAT #2 foundation)**
- **Goal:** Har real command cryptographic governance se guzarna — Decepticon se aage.
- **Method:** `tool_gateway.execute()` mein `executor="sandbox"` path: scope check (post-DNS) → RoE QPS limits → policy evaluation → HMAC token validate → execute → hash-chained audit entry → evidence token attach. Interactive sessions ke liye prompt-detection heuristics + `send_input(session_id, text)` API + `/api/sandbox/session/{id}/input` endpoint.
- **Reference:** `backend/tool_gateway.py`, `backend/policy_engine.py`, `backend/evidence_engine.py`, `backend/server.py`

**Step 3: Signed Engagement Package (BEAT #2 complete)**
- **Goal:** Decepticon jaisa RoE/ConOps/OPPLAN — lekin cryptographically signed.
- **Method:** `mission_engine.py` mein `generate_engagement_package(manifest)`: RoE (scope/RoE fields), ConOps (6-hero roster + kill-chain phases), OPPLAN (GDT goals → MITRE ATT&CK mapping), Deconfliction notes. HMAC signature embed (policy engine key se) taaki doc tamper-evident ho. `/api/mission/package` endpoint.
- **Reference:** `backend/mission_engine.py`, `backend/server.py`

## Track B — BEAT: Leapfrog Features

**Step 4: Offensive Vaccine Loop — SHIPPED (BEAT #1, flagship)**
- **Goal:** Decepticon ka planned feature humara working feature: attack → defend → verify → patch → regression.
- **Method:** Naya `backend/vaccine_engine.py` jo existing engines ko loop mein orchestrate kare: (1) VORTEX finding → evidence anchor, (2) defense_engine se sigma-style rule synthesize, (3) sandbox mein attack replay vs. rule — detect hua? (4) nahi hua toh CIPHER-MORPH entropy mutation se escalate (max 3, circuit breaker), (5) detect hua toh self_healing_engine se patch draft + regression-gated lesson store. Endpoints: `/api/vaccine/run|status|report`. Har cycle ka verdict evidence-chained.
- **Reference:** new `backend/vaccine_engine.py`, `backend/defense_engine.py`, `backend/self_healing_engine.py`, `backend/evidence_engine.py`, `backend/sandbox_engine.py`

**Step 5: Hybrid World Model Persistence (BEAT #3)**
- **Goal:** Neo4j jaisi durability, bina uski latency ke.
- **Method:** `cypher_engine.py` mein write-through journal (append-only JSONL + snapshot-on-interval) aur startup replay; optional Neo4j sync adapter behind env flag (`NEO4J_URI`) jo async queue se graph replicate kare — queries hamesha in-memory 23μs engine se, persistence background mein. MCP `/mcp/world-model` restore-aware banana.
- **Reference:** `backend/cypher_engine.py`, `docker-compose.yml` (optional neo4j service), `backend/server.py`

**Step 6: Self-Improving Evasion Memory (BEAT #4)**
- **Goal:** Swarm engagements ke beech seekhe — Decepticon stateless hai.
- **Method:** Vaccine loop (Step 4) ke har mutation outcome ko `strategy_memory` + `vector_memory` mein lesson ke roop mein store karna; CIPHER-MORPH payload synthesis se pehle `vector_memory.recall(payload_context)` se similar past failures retrieve karke entropy/mutation strategy adjust karna. `/api/memory/vector/recall` ko agents.py ke CIPHER-MORPH flow mein wire karna.
- **Reference:** `backend/agents.py`, `backend/strategy_memory.py`, `backend/vector_memory.py`, `cython_core/fast_entropy.pyx`

**Step 7: Tavily Live Threat Research Engine (BEAT #6, flagship)**
- **Goal:** Agents ko real-time hacking-technology research dena — Decepticon ke agents sirf static model knowledge use karte hain.
- **Method:** Naya `backend/intel_engine.py`: Tavily Search API client (`TAVILY_API_KEY` env se, `httpx` async), 3 research modes — (1) **CVE/Exploit Intel:** fingerprinted service/version → latest CVEs, PoC writeups, exploit-db references, (2) **TTP Research:** MITRE technique → latest real-world abuse patterns & detection notes, (3) **OSINT Enrichment:** domain/org → breach data, tech-stack, exposure reports. Results: summarized + source-cited, `vector_memory` mein store (semantic recall), relevant vulnerabilities `cypher_engine` World Model mein inject. Agent wiring: SPECTRE-RECON (OSINT), VORTEX-EXPLOIT (CVE research before payload synthesis), CHRONO-DEBRIEF (latest remediation guidance). Endpoints: `/api/intel/research|cve/{id}|osint|stats`. Offline grace: no key → cached lessons + static skills fallback.
- **Reference:** new `backend/intel_engine.py`, `backend/agents.py`, `backend/vector_memory.py`, `backend/cypher_engine.py`, `backend/server.py`, `docker-compose.yml` (TAVILY_API_KEY env)

**Step 8: Sonic Speed Layer (BEAT #7)**
- **Goal:** Full recon+research cycle sub-60s; Decepticon ke sequential LangGraph loop se tez.
- **Method:** (1) **Parallel GDT:** `mission_engine.py` mein independent DAG branches `asyncio.gather` se concurrent (circuit breakers preserved), (2) **Batch recon:** `live_scanner.py` mein semaphore-bounded mass-port probing + connection reuse (target: 25 ports < 3s), (3) **Cython fast-paths:** `fast_entropy.pyx` pattern reuse karke banner-parsing/JSON canonicalization ko compiled path dena (pure-Python fallback intact), (4) **Intel cache:** Tavily results ko TTL cache (vector_memory disk persistence reuse) — duplicate research queries zero-latency, (5) **Swarm bus batching:** high-frequency telemetry ko micro-batch dispatch (<0.1ms IPC claim preserve). Benchmarks: `/api/benchmark/report` mein latency metrics.
- **Reference:** `backend/mission_engine.py`, `backend/live_scanner.py`, `cython_core/`, `backend/intel_engine.py`, `backend/swarm_bus.py`

**Step 9: Fresh-Context Goal Execution (PARITY++)**
- **Goal:** Decepticon ka fresh-context-per-objective pattern GDT par.
- **Method:** `agents.py` mein GDT node execution ko isolated context dict ke saath run karna (no accumulated chat noise); node output sirf structured Pydantic result ke roop mein parent ko — malformed output par retry (existing failure-mode table ke mutabik). Tavily research results ko node context mein curated summary ke roop mein inject karna (raw dump nahi — context bloat avoid).
- **Reference:** `backend/agents.py`, `backend/mission_engine.py`, `backend/intel_engine.py`

## Track C — PROVE: Benchmarks & Distribution

**Step 10: Dual-Axis Public Benchmark (BEAT #5)**
- **Goal:** Decepticon ke 98.08% ko challenge karna + wo dena jo unhone kabhi publish nahi kiya: safety score.
- **Method:** `benchmarks/` dir mein target manifests (OWASP Juice Shop compose + 2–3 DVWA/WebGoat-class targets, expected-vuln checklists ke saath). `benchmark_engine.py` mein external-target mode: mission launch → findings → checklist scoring. Report mein 2 axes: **Attack Pass-Rate** aur **Safety/Compliance Score** (scope leaks=0, collateral=0, policy violations=0, audit-chain integrity). README mein Decepticon-comparison table.
- **Reference:** `backend/benchmark_engine.py`, new `benchmarks/`, `README.md`

**Step 11: Packaging & Plugin Surface**
- **Goal:** Decepticon jaisi installability — `pip install redops-ai`.
- **Method:** `pyproject.toml` (uv-compatible), skills ko declarative plugin-bundle format mein load karne ka surface (`skills_engine` mein `load_bundle(path)`), `.env.example` (incl. `TAVILY_API_KEY`, `NEO4J_URI`), CHANGELOG.md. README ko "Why RedOps beats Decepticon" section ke saath update (vaccine loop + live intel + dual-axis benchmark highlight).
- **Reference:** new `pyproject.toml`, `backend/skills_engine.py`, `README.md`, new `.env.example`

**Step 12: Tests & Regression Safety**
- **Goal:** Sab naye features tested, 36 existing tests green.
- **Method:** Naye pytest integration tests: vaccine loop end-to-end (mock sandbox), governed exec (mock docker SDK), hybrid persistence (journal replay), intel engine (mocked Tavily responses + offline fallback), sonic layer (parallel GDT timing assertions, cache hit behavior), dual-axis benchmark scoring, engagement package signature verify. CI-friendly (docker/Tavily mocked jahan daemon/key na ho).
- **Reference:** `tests/test_vaccine_engine.py`, `tests/test_governed_exec.py`, `tests/test_hybrid_graph.py`, `tests/test_intel_engine.py`, `tests/test_sonic_layer.py`, `tests/`

# 5. TESTING AND VALIDATION

**Regression (must-pass):**
1. `python -m pytest tests/ -v` — existing 36 tests sab green; naye tests ke saath total count badhe, koi skip/xfail nahi.

**Track A (parity) validation:**
2. Sandbox se `nmap -sV <in-scope-lab-target>` real run ho; audit ledger mein hash-chained entry + evidence token bane.
3. Out-of-scope target / policy-blocked command executor tak pahunche hi nahi (negative test).
4. Interactive session: persistent shell mein multi-step sequence (prompt detect → input → output) complete ho.
5. Engagement package markdown mein RoE + OPPLAN + MITRE mapping + valid HMAC signature ho; tampered doc verify fail ho.

**Track B (beat) validation:**
6. **Vaccine loop:** Juice Shop-class target par ek finding se full cycle chale — defense rule bane, attack replay se detect ho, patch draft evidence-anchored ho, lesson regression-gated store ho. `/api/vaccine/report` mein closed-loop verdict dikhe. (Yeh wo cheez hai jo Decepticon mein exist hi nahi karti.)
7. **Hybrid graph:** restart ke baad world model journal se restore ho; BFS latency < 50μs rahe.
8. **Learning evasion:** do consecutive vaccine cycles mein doosre cycle ka mutation pehle cycle ke recalled lessons se influenced ho (trace se verify).
9. **Tavily intel engine:** fingerprinted service (jaise "Apache 2.4.49") diya toh `/api/intel/research` latest CVEs + PoC references + cited sources return kare; same query dobara dene par cache se zero-latency response; `TAVILY_API_KEY` ke bina graceful fallback chale.
10. **Sonic speed:** 25-port recon sweep < 3s; 3+ independent GDT branches wall-clock time mein sequential se measurably faster complete hon (timing test se verify); duplicate intel query cache-hit ho.

**Track C (prove) validation:**
11. Benchmark harness run: attack pass-rate + safety score dono `/api/benchmark/report` mein — safety score 100% (zero scope leak, zero collateral) ke bina report "publishable" flag na set kare; latency metrics bhi report mein hon.
12. `pip install .` se package build/install ho aur `redops --mode cli` entry point chale.

**Final beat-criteria (definition of done):** Ek single demo flow — signed engagement package generate → **Tavily live intel se enriched** governed real scan (sub-60s recon+research) → finding → vaccine loop closes the hole → signed evidence report → dual-axis benchmark — end-to-end chale. Decepticon is flow ka sirf pehla hissa kar sakta hai — woh bina live intel ke, slower, aur bina defense-closure ke.
