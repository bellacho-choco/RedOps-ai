"""
====================================================================
PROJECT REDOPS-AI - 6 SPECIALIZED AGENT HEROES MATRIX (LIVE ENGINE)
Real Autonomous Security Swarm with Real Socket Probes, SAST & LLM Reasoning
====================================================================
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional

from backend.swarm_bus import swarm_bus, AgentMessage
from backend.cypher_engine import graph_engine
from backend.skills_engine import skills_engine
from backend.llm_provider import llm_provider
from backend.live_scanner import socket_scanner, web_auditor, dns_auditor
from backend.sast_analyzer import sast_auditor
from cython_core.fast_entropy import (
    calculate_shannon_entropy,
    polymorphic_mutation_sim,
    is_cython_accelerated
)


class BaseHeroAgent:
    """
    Base Agent Hero archetype with dedicated message queue,
    state machine, and live terminal stream emitter.
    """
    def __init__(self, codename: str, role: str, color_hex: str, specialization: str):
        self.codename = codename
        self.role = role
        self.color_hex = color_hex
        self.specialization = specialization
        self.status = "IDLE"
        self.current_task = "Awaiting mission directive"
        self.queue: Optional[asyncio.Queue] = None
        self.terminal_logs: List[Dict[str, Any]] = []
        self.task_history: List[str] = []

    def initialize(self):
        self.queue = swarm_bus.subscribe(self.codename)
        self.log(f"⚡ [CORE] Neural state initialized. Sub-ms IPC link online.")

    def log(self, text: str, level: str = "INFO", meta: Optional[Dict[str, Any]] = None):
        entry = {
            "timestamp": time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}",
            "agent": self.codename,
            "level": level,
            "text": text,
            "meta": meta or {}
        }
        self.terminal_logs.append(entry)
        if len(self.terminal_logs) > 300:
            self.terminal_logs.pop(0)

    async def emit_to_bus(self, target: str, event_type: str, content: str, meta: Optional[Dict[str, Any]] = None) -> float:
        msg = AgentMessage(
            message_id=str(uuid.uuid4())[:8],
            source_agent=self.codename,
            target_agent=target,
            event_type=event_type,
            content=content,
            meta=meta or {},
            timestamp_ns=time.time_ns()
        )
        latency_ms = await swarm_bus.publish(msg)
        self.log(f"📡 [IPC -> {target}] ({event_type}) in {latency_ms:.3f}ms: {content[:90]}")
        return latency_ms

    async def process_task(self, instruction: str) -> str:
        raise NotImplementedError


# ====================================================================
# HERO 1: OVERLORD-PRIME (Commander & Swarm Orchestrator)
# ====================================================================
class OverlordPrimeAgent(BaseHeroAgent):
    def __init__(self):
        super().__init__(
            codename="OVERLORD-PRIME",
            role="Supreme Mission Commander",
            color_hex="#FF0055",
            specialization="MITRE Kill-Chain Pathfinding & LLM Swarm Orchestration"
        )
        self.mission_phase = "STANDBY"
        self.last_assessment_report = ""

    async def execute_mission(self, target_scope: str = "127.0.0.1") -> Dict[str, Any]:
        self.status = "EXECUTING"
        self.mission_phase = "PHASE_1_RECON"
        skills = skills_engine.get_skills_for_agent(self.codename)
        llm_stat = llm_provider.get_status()

        self.log(f"👑 [MISSION START] Deploying Swarm Operation against: {target_scope}")
        self.log(f"🤖 [LLM REASONER] Provider: {llm_stat['provider']} | Model: {llm_stat['model']} | Mode: {llm_stat['active_mode']}")
        self.log(f"📚 [PLAYBOOKS] Active playbooks loaded: {len(skills)} indexed frameworks")

        # 1. Dispatch Real Network Discovery to SPECTRE-RECON
        await self.emit_to_bus(
            "SPECTRE-RECON",
            "TASK_DISCOVER_TARGET",
            f"Execute live async socket probing and DNS enumeration on: {target_scope}",
            {"target": target_scope}
        )

        recon_result = await swarm_matrix.spectre.handle_live_recon(target_scope)

        # 2. Map Dynamic Graph Topology via NEXUS-CYPHER
        self.mission_phase = "PHASE_2_TOPOLOGY"
        await self.emit_to_bus(
            "NEXUS-CYPHER",
            "TASK_MAP_TOPOLOGY",
            f"Ingest {recon_result.get('open_ports_count', 0)} open services into in-memory attack graph",
            {"scan_data": recon_result}
        )
        await swarm_matrix.nexus.ingest_and_map(recon_result)

        # 3. Web & Vulnerability Audit via VORTEX-EXPLOIT
        self.mission_phase = "PHASE_3_VULN_SYNTHESIS"
        await self.emit_to_bus(
            "VORTEX-EXPLOIT",
            "TASK_AUDIT_SECURITY",
            f"Audit web posture, security headers, and TLS ciphers for {target_scope}",
            {"target": target_scope, "open_ports": recon_result.get("open_ports", [])}
        )
        vuln_result = await swarm_matrix.vortex.handle_vuln_audit(target_scope, recon_result)

        # 4. Secret & SAST Entropy Scan via CIPHER-MORPH
        self.mission_phase = "PHASE_4_ENTROPY"
        await self.emit_to_bus(
            "CIPHER-MORPH",
            "TASK_ANALYZE_ENTROPY",
            f"Execute Cython-speed Shannon entropy & secret pattern sweep on service responses",
            {"target": target_scope}
        )
        sast_result = await swarm_matrix.cipher_morph.handle_sast_scan(target_scope, vuln_result)

        # 5. Compile Executive Debrief via CHRONO-DEBRIEF
        self.mission_phase = "PHASE_5_DEBRIEF"
        combined_context = {
            "target": target_scope,
            "open_ports": recon_result.get("open_ports", []),
            "web_audit": vuln_result,
            "sast_audit": sast_result,
            "scan_duration_s": recon_result.get("scan_duration_s", 0)
        }

        await self.emit_to_bus(
            "CHRONO-DEBRIEF",
            "TASK_GENERATE_DEBRIEF",
            "Synthesize comprehensive mitigation report and MITRE ATT&CK defensive mapping",
            combined_context
        )
        debrief_report = await swarm_matrix.chrono.synthesize_debrief(combined_context)
        self.last_assessment_report = debrief_report

        self.status = "IDLE"
        self.mission_phase = "MISSION_ACCOMPLISHED"
        self.log(f"🏆 [MISSION COMPLETED] Comprehensive assessment report ready for {target_scope}!")
        return {
            "status": "COMPLETED",
            "target": target_scope,
            "scan_data": recon_result,
            "vuln_data": vuln_result,
            "sast_data": sast_result,
            "report": debrief_report
        }

    async def process_task(self, instruction: str) -> str:
        self.log(f"🧠 [DIRECTIVE RECEIVED] {instruction}")
        target = "127.0.0.1"
        for word in instruction.split():
            if "." in word or "http" in word or "localhost" in word:
                target = word
                break
        res = await self.execute_mission(target)
        return f"Mission Completed for {target}. Open ports: {res['scan_data'].get('open_ports_count', 0)}"


# ====================================================================
# HERO 2: SPECTRE-RECON (Surface & Protocol Hunter)
# ====================================================================
class SpectreReconAgent(BaseHeroAgent):
    def __init__(self):
        super().__init__(
            codename="SPECTRE-RECON",
            role="Surface & Protocol Hunter",
            color_hex="#00F0FF",
            specialization="Real-time Async Socket Scanning & DNS Auditing"
        )

    async def handle_live_recon(self, target: str) -> Dict[str, Any]:
        self.status = "SCANNING"
        skills = skills_engine.get_skills_for_agent(self.codename)
        self.log(f"🛰️ [SOCKET PROBE] Launching live async TCP sweep on {target}...")
        
        # Clean host target
        host = target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        if host == "localhost":
            host = "127.0.0.1"

        scan_res = await socket_scanner.scan_target(host)
        self.log(f"✅ [PROBE COMPLETED] Scanned {scan_res['total_probed']} ports in {scan_res['scan_duration_s']}s.")

        open_ports = scan_res.get("open_ports", [])
        if open_ports:
            for p in open_ports:
                self.log(f"🔍 [PORT {p['port']}/TCP OPEN] Service: {p['service']} | Latency: {p['latency_ms']}ms | Banner: {p['banner'][:60]}")
        else:
            self.log(f"ℹ️ [PROBE RESULT] No common open ports detected on {host}.")

        # DNS Audit if domain
        if not host.replace(".", "").isdigit():
            dns_res = dns_auditor.audit_domain(host)
            if dns_res.get("a_records"):
                self.log(f"🌐 [DNS A-RECORDS] {', '.join(dns_res['a_records'])}")
            if dns_res.get("spf_status") != "MISSING":
                self.log(f"🛡️ [DNS SPF] {dns_res['spf_status']}")

        self.status = "IDLE"
        return scan_res

    async def process_task(self, instruction: str) -> str:
        parts = instruction.split()
        target = parts[-1] if parts else "127.0.0.1"
        res = await self.handle_live_recon(target)
        return f"Recon finished. Found {res.get('open_ports_count', 0)} open ports."


# ====================================================================
# HERO 3: NEXUS-CYPHER (Graph Topology Navigator)
# ====================================================================
class NexusCypherAgent(BaseHeroAgent):
    def __init__(self):
        super().__init__(
            codename="NEXUS-CYPHER",
            role="Graph Topology Navigator",
            color_hex="#00FF66",
            specialization="Dynamic Target Graph Ingestion & Shortest Exposure Path"
        )

    async def ingest_and_map(self, scan_data: Dict[str, Any]):
        self.status = "COMPUTING"
        self.log("🧬 [GRAPH AGENT] Ingesting live scan data into in-memory attack graph...")
        graph_engine.ingest_live_scan(scan_data)
        
        target = scan_data.get("target", "target")
        host_id = f"host-{target}"
        self.log(f"⚡ [TOPOLOGY UPDATED] Node [{host_id}] dynamically linked to {scan_data.get('open_ports_count', 0)} service nodes.")
        self.status = "IDLE"

    async def process_task(self, instruction: str) -> str:
        self.log(f"🧬 Executing Cypher query: {instruction}")
        res = graph_engine.execute_query(instruction)
        return f"Cypher Execution: {res.get('summary', 'Query OK')}"


# ====================================================================
# HERO 4: VORTEX-EXPLOIT (Vuln & Logic Flaw Synthesizer)
# ====================================================================
class VortexExploitAgent(BaseHeroAgent):
    def __init__(self):
        super().__init__(
            codename="VORTEX-EXPLOIT",
            role="Vuln & Security Header Auditor",
            color_hex="#FF9900",
            specialization="HTTP Header Posture, TLS Cipher Inspection & Risk Correlation"
        )

    async def handle_vuln_audit(self, target: str, recon_data: Dict[str, Any]) -> Dict[str, Any]:
        self.status = "AUDITING"
        url = target if target.startswith("http") else f"http://{target}"
        
        # Check if HTTP/HTTPS ports are open
        open_ports = [p["port"] for p in recon_data.get("open_ports", [])]
        if 443 in open_ports or 8443 in open_ports:
            url = target if target.startswith("https") else f"https://{target}"

        self.log(f"⚡ [WEB AUDIT START] Probing endpoint security for {url}...")
        web_res = await web_auditor.audit_url(url)
        
        if web_res.get("status_code", 0) > 0:
            self.log(f"🎯 [HTTP RESPONSE] Status: {web_res['status_code']} | Server: {web_res['technology_stack'].get('server')}")
            missing = web_res.get("missing_security_headers", [])
            if missing:
                self.log(f"⚠️ [MISSING HEADERS] {', '.join(missing[:4])} (Total {len(missing)} missing)")
            for r in web_res.get("security_risks", []):
                self.log(f"🚨 [RISK FLAGGED] [{r['severity']}] {r['title']}")

        # Ingest risks into graph
        if web_res.get("security_risks"):
            graph_engine.ingest_live_scan({
                "target": target,
                "open_ports": recon_data.get("open_ports", []),
                "web_audit": web_res
            })

        self.status = "IDLE"
        return web_res

    async def process_task(self, instruction: str) -> str:
        parts = instruction.split()
        target = parts[-1] if parts else "http://localhost:8000"
        res = await self.handle_vuln_audit(target, {})
        return f"Web Audit completed. Status: {res.get('status_code', 0)}"


# ====================================================================
# HERO 5: CIPHER-MORPH (SAST & Entropy Engine)
# ====================================================================
class CipherMorphAgent(BaseHeroAgent):
    def __init__(self):
        super().__init__(
            codename="CIPHER-MORPH",
            role="SAST & Entropy Engine",
            color_hex="#AA00FF",
            specialization="Shannon Entropy Analysis, Secret Pattern Search & Obfuscation Detection"
        )

    async def handle_sast_scan(self, target: str, web_data: Dict[str, Any]) -> Dict[str, Any]:
        self.status = "ANALYZING"
        accel_mode = "CYTHON [C-EXTENSION]" if is_cython_accelerated() else "PURE-PYTHON ACCELERATED"
        self.log(f"🛡️ [ENTROPY ENGINE] Active Mode: {accel_mode}")

        findings = []
        # Analyze headers and responses
        headers_str = str(web_data.get("headers_present", {}))
        if headers_str:
            findings = sast_auditor.analyze_buffer(headers_str, source_name="HTTP_Headers")

        self.log(f"🧬 [SAST RESULT] Scanned response buffers. High-entropy/Secret findings: {len(findings)}")
        self.status = "IDLE"
        return {"findings": findings, "findings_count": len(findings)}

    async def process_task(self, instruction: str) -> str:
        # If user supplied a path or text
        parts = instruction.split(" ", 1)
        data = parts[1] if len(parts) > 1 else instruction
        findings = sast_auditor.analyze_buffer(data, source_name="CLI_Input")
        return f"SAST Analysis found {len(findings)} items."


# ====================================================================
# HERO 6: CHRONO-DEBRIEF (Remediation & Defense Architect)
# ====================================================================
class ChronoDebriefAgent(BaseHeroAgent):
    def __init__(self):
        super().__init__(
            codename="CHRONO-DEBRIEF",
            role="Mitigation & Defense Architect",
            color_hex="#FFCC00",
            specialization="Cyber Reasoning Synthesis, MITRE Mapping & Remediation Playbooks"
        )

    async def synthesize_debrief(self, context: Dict[str, Any]) -> str:
        self.status = "DEBRIEFING"
        self.log("🛡️ [DEBRIEF ENGINE] Synthesizing comprehensive security report...")

        # Request AI Cyber Reasoning from Custom LLM Provider
        ai_reasoning = await llm_provider.generate_cyber_reasoning(
            agent_role=self.role,
            task="Synthesize tactical findings into actionable defensive remediation directives.",
            scan_context=context
        )

        self.log(f"📝 [REASONING GENERATED] Generated prioritized mitigation plan.")
        self.status = "IDLE"
        return ai_reasoning

    async def process_task(self, instruction: str) -> str:
        return await self.synthesize_debrief({"target": instruction})


# ====================================================================
# SWARM MATRIX ORCHESTRATOR
# ====================================================================
class SwarmMatrix:
    def __init__(self):
        self.overlord = OverlordPrimeAgent()
        self.spectre = SpectreReconAgent()
        self.nexus = NexusCypherAgent()
        self.vortex = VortexExploitAgent()
        self.cipher_morph = CipherMorphAgent()
        self.chrono = ChronoDebriefAgent()

        self.agents: Dict[str, BaseHeroAgent] = {
            self.overlord.codename: self.overlord,
            self.spectre.codename: self.spectre,
            self.nexus.codename: self.nexus,
            self.vortex.codename: self.vortex,
            self.cipher_morph.codename: self.cipher_morph,
            self.chrono.codename: self.chrono
        }
        self.initialize_all()

    def initialize_all(self):
        for agent in self.agents.values():
            agent.initialize()

    def get_agent(self, codename: str) -> Optional[BaseHeroAgent]:
        return self.agents.get(codename)

    def get_all_status(self) -> Dict[str, Any]:
        return {
            name: {
                "codename": a.codename,
                "role": a.role,
                "status": a.status,
                "color_hex": a.color_hex,
                "specialization": a.specialization,
                "log_count": len(a.terminal_logs),
                "latest_log": a.terminal_logs[-1]["text"] if a.terminal_logs else "Ready."
            }
            for name, a in self.agents.items()
        }


# Singleton Matrix Instance
swarm_matrix = SwarmMatrix()
