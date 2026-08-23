# REDOPS-Ω — Getting Started

Governed autonomous adversarial-security intelligence. Every offensive
action routes through the **Policy Engine → Tool Gateway → hash-chained
Audit Ledger**. Non-negotiable.

## 1. Bootstrap

```bash
git clone <repo> && cd RedOps-ai
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional keys (TAVILY / NEO4J / DOCKER)
```

## 2. Launch the governed core

```bash
uvicorn backend.server:app --host 0.0.0.0 --port 12000
```

OpenAPI: `http://localhost:12000/docs`

## 3. First authorized mission (authorized lab targets only!)

```bash
curl -X POST localhost:12000/api/mission/launch -H 'Content-Type: application/json' -d '{
  "manifest": {
    "name": "first-engagement",
    "target_scope": {"domains": ["lab.example"]},
    "rules_of_engagement": {"max_qps": 2, "zero_collateral_policy": true}
  },
  "target": "lab.example"
}'
```

## 4. Consume the Goal Dependency Tree — parallel frontier rounds

```bash
curl -X POST localhost:12000/api/gdt/parallel_dispatch
```

## 5. Flagship attacks you cannot get elsewhere

| Capability | Endpoint |
|---|---|
| Offensive Vaccine Loop | `POST /api/vaccine/run` |
| Live Threat Research (Tavily) | `POST /api/intel/research` |
| Real container sandbox | `POST /api/sandbox/session/open` |
| Signed engagement package | `POST /api/mission/package` |
| Batch recon fanout | `POST /api/recon/batch` |

## 6. Benchmarks — dual-axis (AttackAccuracy × SafetyCompliance)

```bash
uvicorn backend.server:app --port 12000 &
python benchmarks/redops_satellite.py --base-url http://localhost:12000 --target lab.example
```

## 7. Safety contract

* No ACTIVE mission → **Tool Gateway sealed** (all actions denied).
* Out-of-scope target → **denied pre-execution**, post-DNS resolve.
* MITRE high-risk technique → **human cryptographic approval gate**.
* All executions → hash-chained `AuditRecord` with evidence tokens.
