"""
====================================================================
PROJECT REDOPS-OMEGA - SANDBOX ARCHITECTURE
Disposable Validation Labs: Containerized Dry-Run Tier, Virtualized
AD Rehearsal Tier & Client-Side Payload Tier. Blueprint Section 9.

Every validation is a NON-DESTRUCTIVE dry-run: payloads are analyzed
(statically, entropically, against the World Model) — never executed
against live infrastructure from this engine.
====================================================================
"""

import re
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field

from backend.defense_engine import defense_engine
from backend.attack_path_engine import counterfactual_simulator
from backend.cypher_engine import graph_engine
from cython_core.fast_entropy import calculate_shannon_entropy


class SandboxTier(str, Enum):
    CONTAINER_LAB = "CONTAINER_LAB"          # exploit syntax/compile dry-runs
    VIRTUALIZED_LAB = "VIRTUALIZED_LAB"      # AD attack-chain rehearsal on World Model
    BROWSER_SANDBOX = "BROWSER_SANDBOX"      # client-side injection static evaluation


class DryRunVerdict(str, Enum):
    SAFE = "SAFE"                      # benign payload, no hazards
    SUSPICIOUS = "SUSPICIOUS"          # evasion markers / entropy anomaly
    MALICIOUS = "MALICIOUS"            # matches attack signatures
    CHAIN_VIABLE = "CHAIN_VIABLE"      # AD rehearsal reached crown jewel
    CHAIN_DEAD_END = "CHAIN_DEAD_END"  # rehearsal path collapsed


class SandboxResult(BaseModel):
    run_id: str = Field(default_factory=lambda: f"sbx-{uuid.uuid4().hex[:8]}")
    tier: SandboxTier
    verdict: DryRunVerdict
    subject: str
    entropy: float = 0.0
    matched_rules: List[str] = Field(default_factory=list)
    chain_narrative: str = ""
    reachable_crown_jewels: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    executed_at: float = Field(default_factory=time.time)
    elapsed_ms: float = 0.0


# Syntax sanity patterns for the container tier (common exploit primitives).
_COMPILE_MARKERS = re.compile(
    r"(import\s+(os|sys|socket|subprocess)|#!/usr/bin/(env\s+)?(python|bash)|"
    r"CREATE\s+(OR\s+REPLACE\s+)?FUNCTION|contract\s+\w+\s*\{|public\s+static\s+void)",
    re.I,
)


class RemoteSandboxNode(BaseModel):
    """A distributed sandbox lab registered under Phase II federation."""
    node_id: str = Field(default_factory=lambda: f"sbx-node-{uuid.uuid4().hex[:6]}")
    endpoint: str                                  # e.g. https://lab-grid-01.internal:9443
    tier: SandboxTier = SandboxTier.CONTAINER_LAB
    capacity: int = 4
    registered_at: float = Field(default_factory=time.time)
    healthy: bool = True


class SandboxManager:
    """
    Coordinates the three disposable lab tiers. All tiers share one rule:
    analyze, never detonate.
    """
    def __init__(self):
        self.history: List[SandboxResult] = []
        self.remote_nodes: Dict[str, RemoteSandboxNode] = {}

    # ---- Phase II: distributed sandbox grid --------------------------
    def register_remote_node(self, endpoint: str,
                             tier: SandboxTier = SandboxTier.CONTAINER_LAB,
                             capacity: int = 4) -> RemoteSandboxNode:
        node = RemoteSandboxNode(endpoint=endpoint, tier=tier, capacity=capacity)
        self.remote_nodes[node.node_id] = node
        return node

    def deregister_remote_node(self, node_id: str) -> bool:
        return self.remote_nodes.pop(node_id, None) is not None

    def grid_status(self) -> Dict[str, Any]:
        return {
            "local_tiers": [t.value for t in SandboxTier],
            "remote_nodes": [n.model_dump() for n in self.remote_nodes.values()],
            "grid_capacity": sum(n.capacity for n in self.remote_nodes.values() if n.healthy),
        }

    # ----------------------------------------------------------------
    # Tier 1: Containerized Linux Lab (exploit dry-run)
    # ----------------------------------------------------------------
    def dry_run_exploit(self, payload: str, name: str = "payload") -> SandboxResult:
        started = time.perf_counter()
        verdict = defense_engine.inspect(payload)
        entropy = verdict.entropy
        notes: List[str] = []

        if _COMPILE_MARKERS.search(payload):
            notes.append("recognized exploit/source syntax markers")
        if entropy > 7.2:
            notes.append("high entropy: packed/encrypted body suspected")
        elif entropy > 5.5:
            notes.append("moderate entropy: possible encoding layer")

        if verdict.matched_rules:
            final = DryRunVerdict.MALICIOUS
        elif verdict.entropy_anomaly:
            final = DryRunVerdict.SUSPICIOUS
        else:
            final = DryRunVerdict.SAFE

        result = SandboxResult(
            tier=SandboxTier.CONTAINER_LAB, verdict=final, subject=name,
            entropy=entropy, matched_rules=verdict.matched_rules, notes=notes,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self.history.append(result)
        return result

    # ----------------------------------------------------------------
    # Tier 2: Virtualized Lab (AD / attack-chain rehearsal)
    # ----------------------------------------------------------------
    def rehearse_attack_chain(self, seed_node: str) -> SandboxResult:
        """
        Rehearse a lateral-movement chain against the in-memory World
        Model clone — the AD-lab equivalent of detonating in a VM snapshot.
        """
        started = time.perf_counter()
        sim = counterfactual_simulator.simulate_compromise(seed_node)
        viable = bool(sim.reachable_crown_jewels)

        notes = []
        if seed_node not in graph_engine.nodes:
            notes.append("seed node absent from World Model; rehearsal inconclusive")

        result = SandboxResult(
            tier=SandboxTier.VIRTUALIZED_LAB,
            verdict=DryRunVerdict.CHAIN_VIABLE if viable else DryRunVerdict.CHAIN_DEAD_END,
            subject=seed_node,
            chain_narrative=sim.narrative,
            reachable_crown_jewels=sim.reachable_crown_jewels,
            notes=notes,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self.history.append(result)
        return result

    # ----------------------------------------------------------------
    # Tier 3: Browser Sandbox (client-side payload static evaluation)
    # ----------------------------------------------------------------
    def evaluate_client_payload(self, html_or_script: str,
                                name: str = "client-payload") -> SandboxResult:
        started = time.perf_counter()
        verdict = defense_engine.inspect(html_or_script)
        notes: List[str] = []

        dom_sinks = re.findall(r"(?i)(innerHTML|document\.write|eval\s*\(|location\.hash|postMessage)", html_or_script)
        if dom_sinks:
            notes.append(f"DOM sinks present: {sorted(set(dom_sinks))}")

        if "SIG-XSS-002" in verdict.matched_rules:
            final = DryRunVerdict.MALICIOUS
        elif verdict.matched_rules or dom_sinks:
            final = DryRunVerdict.SUSPICIOUS
        else:
            final = DryRunVerdict.SAFE

        result = SandboxResult(
            tier=SandboxTier.BROWSER_SANDBOX, verdict=final, subject=name,
            entropy=verdict.entropy, matched_rules=verdict.matched_rules, notes=notes,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self.history.append(result)
        return result

    # ----------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        by_tier: Dict[str, int] = {}
        by_verdict: Dict[str, int] = {}
        for r in self.history:
            by_tier[r.tier.value] = by_tier.get(r.tier.value, 0) + 1
            by_verdict[r.verdict.value] = by_verdict.get(r.verdict.value, 0) + 1
        return {
            "total_dry_runs": len(self.history),
            "by_tier": by_tier,
            "by_verdict": by_verdict,
        }


# Global Sandbox Manager
sandbox_manager = SandboxManager()


# ====================================================================
# REAL CONTAINER EXECUTION BACKEND (Step 1: PARITY with Decepticon)
# Ephemeral Kali containers + tmux-style persistent sessions via the
# Docker SDK. Difference vs Decepticon: nothing reaches this executor
# without passing the Tool Gateway's HMAC/scope/audit chain.
# ====================================================================
class SandboxExecResult(BaseModel):
    exec_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")
    command: str
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: float = 0.0
    timed_out: bool = False
    session_id: Optional[str] = None
    prompt_detected: bool = False
    prompt_type: Optional[str] = None


# Prompt-detection heuristics for interactive session flows.
_PROMPT_HINTS = [
    ("shell", re.compile(r"(^|\n)[^\n]*[$#]\s*$")),
    ("msfconsole", re.compile(r"msf\d+.*?>\s*$", re.S)),
    ("sql", re.compile(r"(mysql|postgres|sqlite3?)>\s*$", re.I)),
    ("python", re.compile(r">>>\s*$")),
    ("confirm", re.compile(r"\[(y/n|yes/no)\]\s*$", re.I)),
]


def detect_prompt(output: str) -> Dict[str, Any]:
    """Heuristic: does the output end at an interactive prompt?"""
    tail = output[-200:] if output else ""
    for name, rx in _PROMPT_HINTS:
        if rx.search(tail):
            return {"prompt_detected": True, "prompt_type": name}
    return {"prompt_detected": False, "prompt_type": None}


class DockerSession(BaseModel):
    session_id: str = Field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}")
    container_id: str = ""
    name: str = ""
    created_at: float = Field(default_factory=time.time)
    commands_run: int = 0


class DockerExecutor:
    """
    Real governed container backend. Two execution modes:

    1. Ephemeral runs — one-shot containers for scan/exploit commands,
       resource-capped, auto-destroyed, timeout-enforced.
    2. Persistent sessions — tmux-style long-lived containers supporting
       multi-step interactive sequences with prompt detection.

    The docker SDK/daemon may be absent (CI): every method raises
    RuntimeError('docker unavailable') and available() returns False —
    callers must degrade to the simulation tiers.
    """
    DEFAULT_IMAGE = "kalilinux/kali-rolling:latest"

    def __init__(self, image: Optional[str] = None, network: str = "sandbox-net",
                 client_factory=None):
        import os as _os
        self.image = image or _os.environ.get("REDOPS_SANDBOX_IMAGE", self.DEFAULT_IMAGE)
        self.network = network
        self._client_factory = client_factory  # test seam
        self._client = None
        self.sessions: Dict[str, DockerSession] = {}

    # ----------------------------------------------------------------
    def _get_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        if self._client is None:
            try:
                import docker  # lazy — SDK optional at import time
                self._client = docker.from_env()
            except Exception as exc:
                raise RuntimeError(f"docker unavailable: {exc}") from exc
        return self._client

    def available(self) -> bool:
        try:
            self._get_client().ping()
            return True
        except Exception:
            return False

    # ----------------------------------------------------------------
    # Mode 1: ephemeral one-shot execution
    # ----------------------------------------------------------------
    def run_ephemeral(self, command: str, timeout: float = 30.0,
                      mem_limit: str = "512m", nano_cpus: int = 1_000_000_000,
                      session_id: Optional[str] = None) -> SandboxExecResult:
        client = self._get_client()
        started = time.perf_counter()
        container = client.containers.run(
            self.image, ["bash", "-c", command],
            detach=True, network=self.network,
            mem_limit=mem_limit, nano_cpus=nano_cpus,
            cap_drop=["ALL"],  # least privilege inside the lab
            security_opt=["no-new-privileges"],
        )
        deadline = time.monotonic() + timeout
        timed_out, exit_code = False, -1
        while True:
            container.reload()
            if container.status in ("exited", "dead"):
                exit_code = container.attrs.get("State", {}).get("ExitCode", -1)
                break
            if time.monotonic() > deadline:
                timed_out = True
                try:
                    container.kill()
                except Exception:
                    pass
                exit_code = -9
                break
            time.sleep(0.05)
        stdout = container.logs(stdout=True, stderr=False) or b""
        stderr = container.logs(stdout=False, stderr=True) or b""
        try:
            container.remove(force=True)
        except Exception:
            pass
        result = SandboxExecResult(
            command=command, exit_code=exit_code,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            timed_out=timed_out, session_id=session_id,
            **detect_prompt(stdout.decode(errors="replace")),
        )
        return result

    # ----------------------------------------------------------------
    # Mode 2: persistent tmux-style sessions
    # ----------------------------------------------------------------
    def open_session(self, name: str = "ops") -> DockerSession:
        client = self._get_client()
        session = DockerSession(name=name)
        container = client.containers.run(
            self.image, ["bash"], detach=True, tty=True, stdin_open=True,
            network=self.network, name=f"redops-sbx-{session.session_id}",
            cap_drop=["ALL"], security_opt=["no-new-privileges"],
        )
        session.container_id = container.id
        self.sessions[session.session_id] = session
        return session

    def send_input(self, session_id: str, text: str,
                   timeout: float = 30.0) -> SandboxExecResult:
        """Send one input line to a session; returns output + prompt state."""
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError(f"unknown session {session_id}")
        client = self._get_client()
        container = client.containers.get(session.container_id)
        started = time.perf_counter()
        try:
            code, output = container.exec_run(
                ["bash", "-c", text], demux=True, timeout=timeout)
            stdout = (output[0] or b"").decode(errors="replace")
            stderr = (output[1] or b"").decode(errors="replace")
            timed_out = False
        except Exception as exc:
            code, stdout, stderr, timed_out = -1, "", str(exc), "timed out" in str(exc).lower()
        session.commands_run += 1
        return SandboxExecResult(
            command=text, exit_code=code, stdout=stdout, stderr=stderr,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            timed_out=timed_out, session_id=session_id,
            **detect_prompt(stdout),
        )

    def close_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if not session:
            return False
        try:
            container = self._get_client().containers.get(session.container_id)
            container.remove(force=True)
        except Exception:
            pass
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "available": self.available(),
            "image": self.image,
            "network": self.network,
            "open_sessions": len(self.sessions),
        }


# Global Docker Executor (lazy — degrades to simulation when daemon absent)
docker_executor = DockerExecutor()
