# Changelog

All notable changes to REDOPS-OMEGA are documented here.

## [0.4.0] - 2026-08-23

### Added
- **Plugin Marketplace** (`/api/plugins`): governed publish/install with trust tiers (CORE/PREVIEW/COMMUNITY/UNTRUSTED) and dependency resolution.
- **Global Security Index** (`/api/gsi/score`): composite 0–100 posture score across attack accuracy, safety compliance, defense readiness, lessons depth.
- **Deployment Wizard** (`/api/wizard/preflight`): GO/HOLD/NOT_READY preflight across sandbox, intel, audit ledger, federated lessons.
- **Unified CLI entry**: `redops --mode cli|server` installable entry point.
- **Plugin bundle loader**: `skills_engine.load_bundle(path)` for declarative plugin bundles.

### Changed
- Branding scrub: competitor name removed from code, docs, and skill taxonomy (`skills/standard/adversary`).

## [0.3.0] - 2026-08-23

### Added
- **Offensive Vaccine Loop** (flagship): finding → defense rule synthesis → guided mutation replay (≤3 rounds, circuit breaker) → IMMUNIZED/BLIND_SPOT → patch draft + regression-gated lesson.
- **Live Threat Research Engine** (flagship): Tavily-backed CVE/TTP/OSINT research with TTL cache and graceful NO_KEY degrade.
- **Hybrid World Model**: write-through JSONL journal + replay restore + optional Neo4j write-behind replica (`NEO4J_URI`).
- **Sonic Speed Layer**: bounded parallel GDT dispatch with isolated `LaneContext`, batch recon fan-out, Cymru-style TTL scanner cache, swarm-bus batch dispatch.
- **Dual-axis public benchmark**: AttackAccuracy × SafetyCompliance with satellite client and baseline snapshot.
- **Self-improving evasion**: vaccine mutation outcomes stored as vector-memory lessons guiding future rounds.

## [0.2.0] - 2026-08-23

### Added
- **Real governed execution**: `DockerExecutor` ephemeral Kali runs (resource caps, `cap_drop=ALL`), persistent sessions with prompt detection.
- **Governed tool path**: `sandbox_exec` through full HMAC/scope/audit chain with evidence tokens.
- **Signed engagement package**: RoE/ConOps/OPPLAN + MITRE mapping, HMAC-sealed tamper-evident.
- **Packaging**: `pyproject.toml`, `requirements.txt`, `.env.example`, `GET_STARTED.md`.
