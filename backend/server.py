"""
====================================================================
PROJECT REDOPS-AI - FASTAPI REDOPS MASTER CONTROL SERVER
WebSocket Multiplexing, Real-time 6-Agent Terminal Streams & REST APIs
====================================================================
"""

import asyncio
import json
import os
import time
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from backend.swarm_bus import swarm_bus, AgentMessage
from backend.agents import swarm_matrix
from backend.cypher_engine import graph_engine

app = FastAPI(
    title="PROJECT REDOPS-AI - Neural RedOps Command Matrix",
    version="2.4.0"
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
