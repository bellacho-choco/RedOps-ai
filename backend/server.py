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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from backend.swarm_bus import swarm_bus, AgentMessage
from backend.agents import swarm_matrix
from backend.cypher_engine import graph_engine
from backend.mission_engine import mission_engine, MissionManifest
from backend.policy_engine import policy_engine, ActionRequest, RiskLevel
from backend.tool_gateway import tool_gateway
from backend.live_scanner import socket_scanner, web_auditor, dns_auditor
from backend.sast_analyzer import sast_auditor
from backend.attack_path_engine import attack_path_engine, counterfactual_simulator
from backend.evidence_engine import evidence_engine
from backend.strategy_memory import strategy_memory
from backend.defense_engine import defense_engine, ai_vs_ai_campaign, DetectionRule
from backend.benchmark_engine import benchmark_engine


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

    tool_gateway.register_tool("port_scan", _port_scan)
    tool_gateway.register_tool("http_probe", _http_probe)
    tool_gateway.register_tool("dns_enum", _dns_enum)
    tool_gateway.register_tool("sast_scan", _sast_scan)
    tool_gateway.register_tool("graph_query", _graph_query)


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
