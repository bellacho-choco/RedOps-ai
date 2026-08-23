"""
====================================================================
PROJECT REDOPS-AI - FASTAPI REDOPS MASTER CONTROL SERVER
WebSocket Multiplexing, Real-time 6-Agent Terminal Streams & REST APIs
====================================================================
"""

import asyncio
import base64
import json
import os
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from backend.swarm_bus import swarm_bus, AgentMessage
from backend.agents import swarm_matrix
from backend.cypher_engine import graph_engine
from backend.mission_engine import (mission_engine, MissionManifest,
    generate_engagement_package, verify_engagement_package, EngagementPackage)
from backend.policy_engine import policy_engine, ActionRequest, RiskLevel
from backend.tool_gateway import tool_gateway
from backend.live_scanner import socket_scanner, web_auditor, dns_auditor
from backend.sast_analyzer import sast_auditor
from backend.attack_path_engine import attack_path_engine, counterfactual_simulator
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory
from backend.defense_engine import defense_engine, ai_vs_ai_campaign, DetectionRule
from backend.benchmark_engine import benchmark_engine
from backend.sandbox_engine import sandbox_manager, docker_executor, SandboxTier
from backend.skills_engine import skills_engine
from backend.vector_memory import vector_memory
from backend.self_healing_engine import self_healing_engine
from backend.federated_exchange import federated_exchange
from backend.cognition_daemon import cognition_daemon
from backend.vaccine_engine import vaccine_engine
from backend.intel_engine import intel_engine
from backend.parallel_dispatch import parallel_dispatcher
from backend.plugin_market import plugin_market, PluginBundle
from backend.gsi_engine import gsi_engine
from backend.deployment_wizard import deployment_wizard
from backend.evolution_engine import evolution_engine
from backend.session_engine import session_engine, IdentityContext
from backend.request_forge import request_forge
from backend.api_mapper import api_mapper, Endpoint
from backend.response_analyzer import response_analyzer, Signal
from backend.fuzz_engine import fuzz_engine
from backend.exploit_validator import exploit_validator


def _register_gateway_tools():
    """Bind real recon/audit capabilities into the governed Tool Gateway."""
    async def _port_scan(target: str, **params):
        return await socket_scanner.scan_target(target, ports=params.get("ports"))

    async def _http_probe(target: str, **params):
        url = target if target.startswith("http") else f"http://{target}"
        return await web_auditor.audit_url(url)

    async def _dns_enum(target: str, **params):
        return dns_auditor.audit_domain(target)

    async def _sast_scan(target: str, **params):
        return {"findings": sast_auditor.analyze_buffer(params.get("buffer", target),
                                                        source_name="gateway")}

    async def _graph_query(target: str, **params):
        return graph_engine.execute_query(params.get("query", "MATCH (h:Host) RETURN h"))

    async def _sandbox_exec(target: str, **params):
        """executor="sandbox": real Docker run when daemon reachable; simulation
        dry otherwise. Either way an evidence token is hash-chained on top."""
        command = params.get("command", "id")
        if docker_executor.available():
            exec_result = docker_executor.run_ephemeral(
                command, timeout=params.get("timeout", 30.0))
            mode, payload = "REAL", exec_result.model_dump()
            summary_label = f"exit={exec_result.exit_code}"
        else:
            sim = sandbox_manager.dry_run_exploit(command)
            mode, payload = "SIMULATED", sim.model_dump()
            summary_label = f"verdict={sim.verdict.value}"
        finding = evidence_engine.register_finding(
            f"Sandbox exec: {command[:64]}", target, "TOOL-GATEWAY", "INFO")
        token = evidence_engine.attach_evidence(
            finding.finding_id, "TOOL-GATEWAY", payload,
            artifact_type="sandbox_exec",
            summary=f"{mode} run {summary_label}")
        return {
            "mode": mode, "result": payload,
            "finding_id": finding.finding_id,
            "evidence_token": token.token_id if token else None,
        }

    async def _http_request(target: str, **params):
        rec = await request_forge.send(
            target, method=params.get("method", "GET"),
            identity=params.get("identity", "unauth"),
            params=params.get("params"), json_body=params.get("json"),
            headers=params.get("headers"))
        return {"status": rec.status, "elapsed_ms": rec.elapsed_ms,
                "length": rec.length, "digest": rec.digest,
                "identity": rec.identity, "url": rec.url}

    async def _api_map(target: str, **params):
        base = target if target.startswith("http") else f"https://{target}"
        eps = await api_mapper.map_target(
            base, identity=params.get("identity", "unauth"),
            max_endpoints=params.get("max_endpoints", 100))
        return {"base": base, "endpoints": len(eps),
                "map": [e.__dict__ for e in eps]}

    async def _fuzz_endpoint(target: str, **params):
        ep = Endpoint(url=target, method=params.get("method", "GET"),
                      params=params.get("params", []))
        res = await fuzz_engine.fuzz_endpoint(
            ep, identity=params.get("identity", "unauth"),
            max_requests=params.get("max_requests", 12))
        return {"url": res.url, "requests_sent": res.requests_sent,
                "signals": [s.__dict__ for s in res.signals],
                "elapsed_ms": res.elapsed_ms}

    tool_gateway.register_tool("port_scan", _port_scan)
    tool_gateway.register_tool("http_probe", _http_probe)
    tool_gateway.register_tool("dns_enum", _dns_enum)
    tool_gateway.register_tool("sast_scan", _sast_scan)
    tool_gateway.register_tool("graph_query", _graph_query)
    tool_gateway.register_tool("sandbox_exec", _sandbox_exec)
    tool_gateway.register_tool("http_request", _http_request)
    tool_gateway.register_tool("api_map", _api_map)
    tool_gateway.register_tool("fuzz_endpoint", _fuzz_endpoint)


_register_gateway_tools()

app = FastAPI(
    title="PROJECT REDOPS-OMEGA - Autonomous Adversarial Security Intelligence",
    version="3.0.0-OMEGA"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected WebSocket Clients
connected_websockets: List[WebSocket] = []


class AgentCommandRequest(BaseModel):
    agent: str
    command: str


class MissionStartRequest(BaseModel):
    target_scope: str = "10.0.0.0/16 Enterprise Grid"


class CypherQueryRequest(BaseModel):
    query: str


# ====================================================================
# WEBSOCKET STREAMING & BROADCAST PIPELINE
# ====================================================================
@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)

    # Subscribe this connection to monitor all swarm bus messages
    sub_queue = swarm_bus.subscribe(f"WS_CLIENT_{id(websocket)}")

    try:
        # Send initial snapshot of all 6 agent statuses & graph state
        await websocket.send_text(json.dumps({
            "type": "INITIAL_STATE",
            "agents": swarm_matrix.get_all_status(),
            "graph": graph_engine.get_full_graph_state(),
            "telemetry": swarm_bus.get_telemetry()
        }))

        # Stream task to broadcast new terminal events & bus messages
        while True:
            # Poll from queue with a short timeout to also send periodic heartbeat/telemetry
            try:
                msg: AgentMessage = await asyncio.wait_for(sub_queue.get(), timeout=0.1)
                await websocket.send_text(json.dumps({
                    "type": "AGENT_MESSAGE",
                    "data": msg.model_dump()
                }))
            except asyncio.TimeoutError:
                # Send live telemetry updates
                await websocket.send_text(json.dumps({
                    "type": "TELEMETRY_HEARTBEAT",
                    "telemetry": swarm_bus.get_telemetry(),
                    "agents": swarm_matrix.get_all_status()
                }))
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


# ====================================================================
# REST API ENDPOINTS
# ====================================================================
@app.get("/api/swarm/status")
async def get_swarm_status():
    return {
        "status": "ONLINE",
        "protocol": "REDOPS_AI_IPC",
        "agents": swarm_matrix.get_all_status(),
        "telemetry": swarm_bus.get_telemetry()
    }


@app.post("/api/swarm/start")
async def start_swarm_operation(req: MissionStartRequest):
    asyncio.create_task(swarm_matrix.overlord.execute_mission(req.target_scope))
    return {
        "status": "STARTED",
        "target_scope": req.target_scope,
        "message": "Autonomous RedOps Swarm deployed across all 6 specialized hero agents."
    }


# ---- OMEGA Pipeline Runner (flagship, Phase 4) ---------------------
class OmegaRunRequest(BaseModel):
    target_scope: str = "127.0.0.1"
    export_report: bool = True


@app.post("/api/omega/run")
async def omega_pipeline_run(req: OmegaRunRequest):
    """One-command Omega Pipeline: preflight -> governed mission ->
    environment model -> attack paths -> witness -> claims -> scorecard."""
    from backend.omega_runner import omega_runner
    report = await omega_runner.run(req.target_scope, req.export_report)
    return report.model_dump()


# ---- Trust certificate + skill auto-synthesis (Phase 4) ------------
class TrustCertificateRequest(BaseModel):
    subject: str
    claims: Dict[str, Any]
    evidence_refs: List[str] = Field(default_factory=list)


@app.post("/api/trust/certificate")
async def issue_certificate(req: TrustCertificateRequest):
    from backend.synthesis_engine import issue_trust_certificate
    cert = issue_trust_certificate(req.subject, req.claims, req.evidence_refs)
    return {**cert.model_dump(), "valid": cert.verify()}


@app.post("/api/synthesis/skill")
async def synthesize_skill():
    """Controlled self-improvement: stage a SKILL.md draft from
    regression-tested strategy memory (never auto-promoted)."""
    from backend.synthesis_engine import synthesis_engine
    return synthesis_engine.synthesize().model_dump()


@app.get("/api/synthesis/staged")
async def list_staged_skills():
    from backend.synthesis_engine import synthesis_engine
    return {"staged": synthesis_engine.list_staged()}


@app.post("/api/agent/command")
async def execute_agent_command(req: AgentCommandRequest):
    agent_name = req.agent.upper()
    agent = swarm_matrix.get_agent(agent_name)
    if agent:
        result = await agent.process_task(req.command)
        return {"status": "SUCCESS", "agent": agent_name, "result": result}
    return {"status": "ERROR", "message": f"Agent {agent_name} not found in matrix."}



@app.get("/api/graph/state")
async def get_graph_state():
    return graph_engine.get_full_graph_state()


@app.post("/api/cypher/query")
async def run_cypher_query(req: CypherQueryRequest):
    result = graph_engine.execute_query(req.query)
    return result


# ====================================================================
# OMEGA: MISSION & GOAL SYSTEM
# ====================================================================
class MissionLaunchRequest(BaseModel):
    manifest: MissionManifest
    target: str


@app.post("/api/mission/launch")
async def launch_mission(req: MissionLaunchRequest):
    mission = mission_engine.launch(req.manifest, req.target)
    strategy_memory.push_session_event("OVERLORD-PRIME", f"Mission launched: {req.manifest.name}")
    return {
        "status": "ACTIVE",
        "mission_id": req.manifest.mission_id,
        "goal_tree": mission.gdt.to_dict()
    }


@app.get("/api/mission/state")
async def get_mission_state():
    mission = mission_engine.get_active()
    if not mission:
        return {"status": "NO_ACTIVE_MISSION"}
    return {
        "status": mission.status,
        "manifest": mission.manifest.model_dump(),
        "goal_tree": mission.gdt.to_dict()
    }


@app.post("/api/mission/abort/{mission_id}")
async def abort_mission(mission_id: str):
    ok = mission_engine.abort(mission_id)
    return {"status": "ABORTED" if ok else "NOT_FOUND", "mission_id": mission_id}


# ---- Signed engagement package (RoE/ConOps/OPPLAN, tamper-evident) ----
@app.post("/api/mission/package")
async def mission_package(req: MissionLaunchRequest):
    manifest = req.manifest
    mission = mission_engine.missions.get(manifest.mission_id)
    if not mission:
        mission = mission_engine.launch(manifest, req.target)
    package = generate_engagement_package(
        mission, tool_gateway.policy.token_issuer.raw_secret())
    return package.model_dump()


@app.post("/api/mission/package/verify")
async def mission_package_verify(package: EngagementPackage):
    result = verify_engagement_package(
        package, tool_gateway.policy.token_issuer.raw_secret())
    return result


# ====================================================================
# OMEGA: POLICY ENGINE & TOOL GATEWAY
# ====================================================================
class TokenIssueRequest(BaseModel):
    agent: str
    tool: str
    ttl_s: int = 3600


class GatewayExecRequest(BaseModel):
    action: ActionRequest
    capability_token: str
    approval_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    approval_id: str
    operator: str = "human-engineer"


@app.post("/api/gateway/token")
async def issue_capability_token(req: TokenIssueRequest):
    mission = mission_engine.get_active()
    if not mission:
        return {"status": "ERROR", "message": "No active mission; tokens cannot be minted"}
    token = policy_engine.token_issuer.issue(
        req.agent.upper(), req.tool, mission.manifest.mission_id, ttl_s=req.ttl_s
    )
    return {"status": "ISSUED", "capability_token": token,
            "mission_id": mission.manifest.mission_id}


@app.post("/api/gateway/execute")
async def gateway_execute(req: GatewayExecRequest):
    result = await tool_gateway.execute(
        req.action, capability_token=req.capability_token, approval_id=req.approval_id
    )
    return result


@app.get("/api/gateway/audit")
async def get_audit_trail(limit: int = 50):
    return {"ledger": tool_gateway.get_audit_trail(limit),
            "integrity": tool_gateway.verify_ledger_integrity()}


@app.post("/api/policy/evaluate")
async def policy_evaluate(action: ActionRequest):
    mission = mission_engine.get_active()
    roe = mission.manifest.rules_of_engagement if mission else None
    return policy_engine.evaluate(action, roe=roe).model_dump()


@app.get("/api/policy/approvals")
async def get_pending_approvals():
    return {"pending": policy_engine.pending_approvals()}


@app.post("/api/policy/approve")
async def approve_action(req: ApprovalRequest):
    ticket = policy_engine.approve(req.approval_id, req.operator)
    return {"status": ticket.status if ticket else "NOT_FOUND"}


@app.post("/api/policy/reject")
async def reject_action(req: ApprovalRequest):
    ticket = policy_engine.reject(req.approval_id, req.operator)
    return {"status": ticket.status if ticket else "NOT_FOUND"}


# ====================================================================
# OMEGA: ATTACK-PATH ENGINE & COUNTERFACTUAL SIMULATOR
# ====================================================================
class SimulateRequest(BaseModel):
    seed_node: str


@app.get("/api/attack-paths")
async def get_attack_paths():
    paths = attack_path_engine.enumerate_paths()
    return {
        "total_paths": len(paths),
        "paths": [p.model_dump() for p in paths[:20]]
    }


@app.post("/api/simulate/counterfactual")
async def run_counterfactual(req: SimulateRequest):
    return counterfactual_simulator.simulate_compromise(req.seed_node).model_dump()


# ====================================================================
# OMEGA: WEB EXPLOITATION STACK (session / forge / map / fuzz / validate)
# ====================================================================
class IdentityRegisterRequest(BaseModel):
    name: str
    headers: Dict[str, str] = {}
    bearer: Optional[str] = None
    api_key: Optional[str] = None
    cookies: Dict[str, str] = {}


class ProbeRequest(BaseModel):
    url: str
    method: str = "GET"
    identity: str = "unauth"
    params: Optional[Dict[str, Any]] = None
    json_body: Optional[Any] = None
    headers: Optional[Dict[str, str]] = None


class MapRequest(BaseModel):
    base_url: str
    identity: str = "unauth"
    max_endpoints: int = 100


class FuzzRequest(BaseModel):
    url: str
    method: str = "GET"
    params: List[str] = []
    identity: str = "unauth"
    max_requests: int = 12


class ValidateRequest(BaseModel):
    signal_kind: str
    url: str
    detail: str = ""
    confidence: float = 0.5
    severity: str = "MEDIUM"
    context: Dict[str, Any] = {}
    method: str = "GET"
    identity: str = "unauth"
    params: Optional[Dict[str, Any]] = None


@app.get("/api/session/identities")
async def list_identities():
    return {"identities": session_engine.list_identities()}


@app.post("/api/session/identities")
async def register_identity(req: IdentityRegisterRequest):
    ctx = session_engine.create(req.name, headers=req.headers, bearer=req.bearer,
                                api_key=req.api_key, cookies=req.cookies)
    return {"registered": ctx.name}


@app.post("/api/probe/request")
async def probe_request(req: ProbeRequest):
    rec = await request_forge.send(req.url, method=req.method, identity=req.identity,
                                   params=req.params, json_body=req.json_body,
                                   headers=req.headers)
    signals = response_analyzer.analyze(rec)
    return {"status": rec.status, "elapsed_ms": rec.elapsed_ms, "length": rec.length,
            "digest": rec.digest, "identity": rec.identity,
            "signals": [s.__dict__ for s in signals]}


@app.post("/api/probe/map")
async def probe_map(req: MapRequest):
    eps = await api_mapper.map_target(req.base_url, identity=req.identity,
                                      max_endpoints=req.max_endpoints)
    return {"base": req.base_url, "endpoints": len(eps),
            "map": [e.__dict__ for e in eps]}


@app.post("/api/probe/fuzz")
async def probe_fuzz(req: FuzzRequest):
    ep = Endpoint(url=req.url, method=req.method, params=req.params)
    res = await fuzz_engine.fuzz_endpoint(ep, identity=req.identity,
                                          max_requests=req.max_requests)
    return {"url": res.url, "requests_sent": res.requests_sent,
            "signals": [s.__dict__ for s in res.signals],
            "elapsed_ms": res.elapsed_ms}


@app.post("/api/probe/idor")
async def probe_idor(url: str, identity_a: str = "user_a", identity_b: str = "user_b"):
    signals = await fuzz_engine.idor_check(url, identity_a, identity_b)
    return {"url": url, "signals": [s.__dict__ for s in signals]}


@app.post("/api/probe/validate")
async def probe_validate(req: ValidateRequest):
    signal = Signal(kind=req.signal_kind, url=req.url, detail=req.detail,
                    confidence=req.confidence, severity=req.severity,
                    context=req.context)
    result = await exploit_validator.validate(signal, method=req.method,
                                              identity=req.identity, params=req.params)
    return result.__dict__


@app.get("/api/probe/summary")
async def probe_summary():
    return {"requests": len(request_forge.request_log),
            "recent_requests": request_forge.request_log[-20:],
            "validation": exploit_validator.summary(),
            "endpoints_mapped": {k: len(v) for k, v in api_mapper.maps.items()}}


# ====================================================================
# OMEGA: EVIDENCE & VALIDATION ENGINE
# ====================================================================
class FindingRequest(BaseModel):
    title: str
    target: str
    agent: str
    severity: str = "MEDIUM"


class EvidenceAttachRequest(BaseModel):
    finding_id: str
    agent: str
    artifact: Any
    artifact_type: str = "scan_output"
    summary: str = ""


class ContradictionRequest(BaseModel):
    finding_id: str
    reason: str


@app.post("/api/evidence/finding")
async def register_finding(req: FindingRequest):
    return evidence_engine.register_finding(
        req.title, req.target, req.agent, req.severity
    ).model_dump()


@app.post("/api/evidence/attach")
async def attach_evidence(req: EvidenceAttachRequest):
    token = evidence_engine.attach_evidence(
        req.finding_id, req.agent, req.artifact, req.artifact_type, req.summary
    )
    if not token:
        return {"status": "ERROR", "message": "Finding not found"}
    finding = evidence_engine.findings[req.finding_id]
    return {"status": "ATTACHED", "token": token.model_dump(),
            "finding_state": finding.state, "confidence": finding.confidence,
            "repro_script": finding.repro_script}


@app.post("/api/evidence/contradict")
async def contradict_finding(req: ContradictionRequest):
    finding = evidence_engine.report_contradiction(req.finding_id, req.reason)
    if not finding:
        return {"status": "ERROR", "message": "Finding not found"}
    return {"status": "DOWNGRADED", "state": finding.state,
            "confidence": finding.confidence}


@app.get("/api/evidence/state")
async def get_evidence_state():
    return evidence_engine.get_state_summary()


# ====================================================================
# OMEGA: STRATEGY MEMORY
# ====================================================================
class OutcomeRequest(BaseModel):
    attempt: str
    outcome: str
    tags: List[str] = []
    regression_tested: bool = False


@app.get("/api/memory/stats")
async def get_memory_stats():
    return strategy_memory.get_stats()


@app.post("/api/memory/outcome")
async def record_outcome(req: OutcomeRequest):
    lesson = strategy_memory.record_outcome(
        req.attempt, req.outcome, req.tags, req.regression_tested
    )
    return lesson.model_dump()


@app.get("/api/memory/lessons")
async def search_lessons(q: str = "", limit: int = 10):
    if q:
        return {"lessons": strategy_memory.search_lessons(q, limit)}
    return {"approved": strategy_memory.approved_strategies()}


# ====================================================================
# OMEGA: AI-VS-AI RED TEAMING (DEFENSE ENGINE)
# ====================================================================
class InspectRequest(BaseModel):
    payload: str
    encode_base64: bool = False


class CampaignRequest(BaseModel):
    rounds: int = 10


@app.get("/api/defense/rules")
async def get_defense_rules():
    return {"rules": [r.model_dump() for r in defense_engine.rules.values()],
            "stats": defense_engine.get_stats()}


@app.post("/api/defense/rules")
async def add_defense_rule(rule: DetectionRule):
    defense_engine.add_rule(rule)
    return {"status": "ADDED", "rule_id": rule.rule_id,
            "rules_loaded": len(defense_engine.rules)}


@app.post("/api/defense/inspect")
async def inspect_payload(req: InspectRequest):
    data = req.payload
    if req.encode_base64:
        try:
            data = base64.b64decode(data).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return defense_engine.inspect(data).model_dump()


@app.post("/api/simulate/ai-vs-ai")
async def run_ai_vs_ai_campaign(req: CampaignRequest):
    report = ai_vs_ai_campaign.run(rounds=req.rounds)
    strategy_memory.push_session_event(
        "CHRONO-DEBRIEF",
        f"AI-vs-AI campaign {report.campaign_id}: detection_rate={report.detection_rate}")
    return report.model_dump()


# ====================================================================
# OMEGA: BENCHMARKING FRAMEWORK
# ====================================================================
@app.get("/api/benchmark/report")
async def get_benchmark_report():
    return benchmark_engine.collect().model_dump()


@app.get("/api/benchmark/history")
async def get_benchmark_trend(limit: int = 20):
    return {"trend": benchmark_engine.trend(limit)}

class ExternalBenchmarkRequest(BaseModel):
    manifest_name: str
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    seed: Optional[int] = None
    run_health_check: bool = False


@app.post("/api/benchmark/external")
async def score_external_benchmark(req: ExternalBenchmarkRequest):
    """External-target mode: checklist scoring of mission findings against a
    benchmark target manifest. Optional rot-detection health pre-check and
    seeded deterministic replay; per-finding JSONL trace exported."""
    import json as _json
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "benchmarks", "targets", f"{req.manifest_name}.json")
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="target manifest not found")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = _json.load(f)
    result = benchmark_engine.score_external(manifest, req.findings,
                                             seed=req.seed)
    if req.run_health_check:
        health = benchmark_engine.health_check(manifest)
        result.health = health["health"]
        result.health_detail = health["health_detail"]
        result.scored = health["scored"]
    report = benchmark_engine.collect()
    return {"checklist": result.model_dump(),
            "safety": report.safety.model_dump(),
            "publishable": report.publishable}


@app.get("/api/benchmark/targets")
async def list_benchmark_targets():
    import json as _json
    targets_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "benchmarks", "targets")
    targets = []
    if os.path.isdir(targets_dir):
        for f in sorted(os.listdir(targets_dir)):
            if f.endswith(".json"):
                with open(os.path.join(targets_dir, f), encoding="utf-8") as fh:
                    m = _json.load(fh)
                targets.append({"name": m.get("name"), "image": m.get("image"),
                                "expected_vulns": len(m.get("expected_vulns", []))})
    return {"targets": targets}



# ====================================================================
# OMEGA: SANDBOX ARCHITECTURE (DRY-RUN VALIDATION LABS)
# ====================================================================
class SandboxDryRunRequest(BaseModel):
    payload: str
    name: str = "payload"


class SandboxRehearsalRequest(BaseModel):
    seed_node: str


@app.post("/api/sandbox/dry-run")
async def sandbox_dry_run(req: SandboxDryRunRequest):
    return sandbox_manager.dry_run_exploit(req.payload, req.name).model_dump()


@app.post("/api/sandbox/rehearse")
async def sandbox_rehearse(req: SandboxRehearsalRequest):
    return sandbox_manager.rehearse_attack_chain(req.seed_node).model_dump()


@app.post("/api/sandbox/client-payload")
async def sandbox_client_payload(req: SandboxDryRunRequest):
    return sandbox_manager.evaluate_client_payload(req.payload, req.name).model_dump()


@app.get("/api/sandbox/stats")
async def sandbox_stats():
    return sandbox_manager.get_stats()


# ====================================================================
# OMEGA: MCP INTEGRATION (MODEL CONTEXT PROTOCOL BRIDGE)
# External LLM orchestrators / IDEs consume the World Model, playbook
# index and sandbox validation through these standard endpoints.
# ====================================================================
class McpSandboxValidateRequest(BaseModel):
    payload: str
    tier: str = "CONTAINER_LAB"


@app.get("/mcp/world-model")
async def mcp_world_model():
    return {
        "protocol": "MCP",
        "resource": "redops://world-model",
        "graph": graph_engine.get_full_graph_state(),
        "evidence": evidence_engine.get_state_summary(),
    }


@app.get("/mcp/skills")
async def mcp_skills_index(q: str = "", limit: int = 15):
    if q:
        return {"protocol": "MCP", "resource": "redops://skills",
                "results": skills_engine.search_skills(q, limit)}
    return {"protocol": "MCP", "resource": "redops://skills",
            "summary": skills_engine.get_summary()}


@app.get("/mcp/skills/{skill_name}")
async def mcp_skill_content(skill_name: str):
    content = skills_engine.read_skill_content(skill_name)
    if content is None:
        return {"protocol": "MCP", "status": "NOT_FOUND", "skill": skill_name}
    return {"protocol": "MCP", "resource": f"redops://skills/{skill_name}",
            "content": content}


# ---- Skills audit & MITRE index (Step 12 hardening) -----------------
@app.get("/api/skills/audit")
async def skills_audit():
    return skills_engine.audit()


@app.get("/api/skills/mitre/{technique_id}")
async def skills_mitre_lookup(technique_id: str):
    results = skills_engine.lookup_mitre(technique_id)
    if not results:
        raise HTTPException(status_code=404, detail="no skills mapped to technique")
    return {"technique": technique_id.upper(), "skills": results}


@app.post("/mcp/sandbox/validate")
async def mcp_sandbox_validate(req: McpSandboxValidateRequest):
    tier = req.tier.upper()
    if tier == "BROWSER_SANDBOX":
        result = sandbox_manager.evaluate_client_payload(req.payload)
    elif tier == "VIRTUALIZED_LAB":
        result = sandbox_manager.rehearse_attack_chain(req.payload)
    else:
        result = sandbox_manager.dry_run_exploit(req.payload)
    return {"protocol": "MCP", "tool": "sandbox.validate", "result": result.model_dump()}


# ====================================================================
# OMEGA PHASE II: VECTOR MEMORY + MISSION PERSISTENCE + SANDBOX GRID
# ====================================================================
class VectorRecallRequest(BaseModel):
    query: str
    limit: int = 5
    min_score: float = 0.1


@app.post("/api/memory/vector/recall")
async def vector_recall(req: VectorRecallRequest):
    return {"results": vector_memory.recall_similar(req.query, req.limit, req.min_score)}


@app.get("/api/memory/vector/stats")
async def vector_stats():
    return vector_memory.get_stats()


@app.post("/api/mission/snapshot")
async def mission_snapshot():
    return mission_engine.snapshot()


@app.post("/api/mission/restore")
async def mission_restore():
    return mission_engine.restore()


class SandboxNodeRequest(BaseModel):
    endpoint: str
    tier: str = "CONTAINER_LAB"
    capacity: int = 4


@app.post("/api/sandbox/grid/register")
async def sandbox_grid_register(req: SandboxNodeRequest):
    node = sandbox_manager.register_remote_node(
        req.endpoint, SandboxTier(req.tier.upper()), req.capacity)
    return node.model_dump()


@app.get("/api/sandbox/grid")
async def sandbox_grid():
    return sandbox_manager.grid_status()


# ---- Interactive governed sessions (prompt-detect -> input -> output) ----
class SandboxSessionOpenRequest(BaseModel):
    name: str = "ops"


class SandboxSessionInputRequest(BaseModel):
    text: str
    timeout: float = 30.0


@app.post("/api/sandbox/session/open")
async def sandbox_session_open(req: SandboxSessionOpenRequest):
    if not docker_executor.available():
        return {"status": "UNAVAILABLE", "reason": "docker daemon not reachable; "
                    "simulation tiers remain active"}
    session = docker_executor.open_session(req.name)
    return session.model_dump()


@app.post("/api/sandbox/session/{session_id}/input")
async def sandbox_session_input(session_id: str, req: SandboxSessionInputRequest):
    try:
        result = docker_executor.send_input(session_id, req.text, req.timeout)
    except KeyError:
        return {"status": "NOT_FOUND", "session_id": session_id}
    return result.model_dump()


@app.post("/api/sandbox/session/{session_id}/close")
async def sandbox_session_close(session_id: str):
    closed = docker_executor.close_session(session_id)
    return {"closed": closed, "session_id": session_id}


# ====================================================================
# OMEGA PHASE III: SELF-HEALING + FEDERATED EXCHANGE
# ====================================================================
class HealRequest(BaseModel):
    content: str
    source_name: str = "Buffer"


@app.post("/api/heal/scan")
async def heal_scan(req: HealRequest):
    return self_healing_engine.heal_buffer(req.content, req.source_name)


@app.post("/api/heal/status/{patch_id}")
async def heal_set_status(patch_id: str, status: str = "APPROVED"):
    draft = self_healing_engine.set_status(patch_id, status)
    if not draft:
        return {"status": "NOT_FOUND", "patch_id": patch_id}
    return draft.model_dump()


@app.get("/api/heal/stats")
async def heal_stats():
    return self_healing_engine.get_stats()


@app.get("/api/federation/export")
async def federation_export(limit: int = 50):
    return federated_exchange.export_lessons(limit)


class FederationImportRequest(BaseModel):
    pack: Dict[str, Any]
    trusted_signature: Optional[str] = None


@app.post("/api/federation/import")
async def federation_import(req: FederationImportRequest):
    return federated_exchange.import_lessons(req.pack, req.trusted_signature)


@app.get("/api/federation/stats")
async def federation_stats():
    return federated_exchange.get_stats()


# ====================================================================
# BEAT #2: LIVE THREAT RESEARCH ENGINE (Tavily HTTP connector)
# ====================================================================
class IntelQueryRequest(BaseModel):
    query: str
    depth: str = "basic"
    max_results: int = 5


@app.post("/api/intel/research")
async def intel_research(req: IntelQueryRequest):
    return intel_engine.research(req.query, req.depth, req.max_results).model_dump()


@app.get("/api/intel/cache")
async def intel_cache():
    return intel_engine.get_stats()


# ====================================================================
# BEAT #5: SONIC SPEED LAYER (parallel dispatch, batch recon, caching)
# ====================================================================
async def _default_goal_runner(ctx) -> str:
    """Runner hook: READY lanes run inline against an isolated context."""
    return f"lane {ctx.goal.get('goal_id')} handled by {ctx.agent}"


class BatchReconRequest(BaseModel):
    targets: List[str]
    max_concurrent: int = 8


@app.post("/api/recon/batch")
async def recon_batch(req: BatchReconRequest):
    return await socket_scanner.batch_recon(req.targets, req.max_concurrent)


@app.post("/api/gdt/parallel_dispatch")
async def gdt_parallel_dispatch():
    lanes = await parallel_dispatcher.dispatch(_default_goal_runner)
    return {"dispatched": [l.model_dump() for l in lanes],
            "frontier_done": mission_engine.get_active().gdt.to_dict()
            if mission_engine.get_active() else None}


# ====================================================================
# NEXT-PHASE SATELLITES: PLUGIN MARKETPLACE, GSI SCORING, DEPLOYMENT WIZARD
# ====================================================================
@app.get("/api/plugins")
async def plugin_index():
    return plugin_market.get_stats()


@app.post("/api/plugins/publish")
async def plugin_publish(bundle: PluginBundle):
    return plugin_market.publish(bundle)


@app.post("/api/plugins/install/{name}")
async def plugin_install(name: str):
    return plugin_market.install(name)


@app.get("/api/gsi/score")
async def gsi_score():
    return gsi_engine.score().model_dump()


@app.get("/api/gsi/trend")
async def gsi_trend():
    return gsi_engine.trend()


@app.get("/api/wizard/preflight")
async def wizard_preflight():
    return deployment_wizard.run_preflight().model_dump()


# EVOLUTION ENGINE: continuous self-improvement (posture -> vaccine -> lessons -> re-score)
@app.post("/api/evolution/cycle")
async def evolution_cycle():
    return evolution_engine.run().model_dump()


@app.get("/api/evolution/report")
async def evolution_report():
    return evolution_engine.report()



# ====================================================================
# BEAT #1: OFFENSIVE VACCINE LOOP (attack -> defend -> verify -> patch)
# ====================================================================
class VaccineRunRequest(BaseModel):
    finding: Dict[str, Any]


@app.post("/api/vaccine/run")
async def vaccine_run(req: VaccineRunRequest):
    cycle = vaccine_engine.run_cycle(req.finding)
    return cycle.model_dump()


@app.get("/api/vaccine/report")
async def vaccine_report():
    return vaccine_engine.get_report()


@app.get("/api/vaccine/status/{cycle_id}")
async def vaccine_status(cycle_id: str):
    cycle = vaccine_engine.cycles.get(cycle_id)
    if not cycle:
        return {"status": "NOT_FOUND", "cycle_id": cycle_id}
    return cycle.model_dump()


# ====================================================================
# OMEGA PHASE IV: CONTINUOUS COGNITION DAEMON
# ====================================================================
@app.post("/api/cognition/start")
async def cognition_start():
    return cognition_daemon.start()


@app.post("/api/cognition/stop")
async def cognition_stop():
    return cognition_daemon.stop()


@app.post("/api/cognition/cycle")
async def cognition_cycle():
    return (await cognition_daemon.run_cycle()).model_dump()


@app.get("/api/cognition/state")
async def cognition_state():
    return cognition_daemon.get_state()


# ====================================================================
# STATIC FILE HOSTING (TACTICAL HUD UI)
# ====================================================================
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>PROJECT REDOPS-AI</h1><p>Initializing HUD interface...</p>")
