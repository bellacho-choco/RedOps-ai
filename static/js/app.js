/**
 * REDOPS-AI - Master UI Cockpit Logic & WebSocket Stream Manager
 */

let ws = null;
let graphVisualizer = null;

document.addEventListener('DOMContentLoaded', () => {
    graphVisualizer = new AttackGraphVisualizer('attackGraphCanvas');
    initWebSocket();
    setupEventListeners();
});

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("⚡ [REDOPS-AI] WebSocket sub-ms stream connected.");
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleIncomingStream(data);
        } catch (e) {
            console.error("Stream parse error:", e);
        }
    };

    ws.onclose = () => {
        setTimeout(initWebSocket, 2000);
    };
}

function handleIncomingStream(msg) {
    if (msg.type === 'INITIAL_STATE') {
        updateAllAgents(msg.agents);
        if (graphVisualizer) graphVisualizer.updateGraphData(msg.graph);
        updateTelemetry(msg.telemetry);
    } else if (msg.type === 'TELEMETRY_HEARTBEAT') {
        updateTelemetry(msg.telemetry);
        updateAllAgents(msg.agents);
    } else if (msg.type === 'AGENT_MESSAGE') {
        appendAgentLog(msg.data);
        appendBusPacket(msg.data);
        audioSynth.playPacketChime();
        refreshGraphState();
    }
}

function updateAllAgents(agents) {
    if (!agents) return;
    Object.keys(agents).forEach(name => {
        const agent = agents[name];
        const statEl = document.getElementById(`stat-${name}`);
        if (statEl) {
            statEl.innerText = agent.status;
            statEl.className = agent.status === 'IDLE' ? 'agent-stat' : 'agent-stat active';
        }
    });
}

function appendAgentLog(pkt) {
    const agent = pkt.source_agent;
    const body = document.getElementById(`logs-${agent}`);
    if (!body) return;

    const div = document.createElement('div');
    div.className = 'log-entry';
    const t = new Date().toLocaleTimeString();
    div.innerHTML = `<span class="log-time">[${t}]</span> <span style="color: var(--neon-cyan)">[${pkt.event_type}]</span> ${escapeHtml(pkt.content)}`;

    body.appendChild(div);
    body.scrollTop = body.scrollHeight;

    // Update killchain progress bar dynamically
    updateProgressIndicator(pkt.event_type);
}

function updateProgressIndicator(eventType) {
    const bar = document.getElementById('killchainProgress');
    if (!bar) return;

    if (eventType.includes('DISCOVER')) {
        bar.style.width = '30%';
        setActivePhase('p1');
    } else if (eventType.includes('TOPOLOGY') || eventType.includes('ATTACK_PATH')) {
        bar.style.width = '55%';
        setActivePhase('p2');
    } else if (eventType.includes('FLAW') || eventType.includes('AST')) {
        bar.style.width = '75%';
        setActivePhase('p3');
    } else if (eventType.includes('MUTATION') || eventType.includes('EVASION')) {
        bar.style.width = '90%';
        setActivePhase('p4');
    } else if (eventType.includes('COMPLETED') || eventType.includes('ACCOMPLISHED')) {
        bar.style.width = '100%';
        setActivePhase('p5');
        audioSynth.playCompromiseStinger();
    }
}

function setActivePhase(phaseId) {
    document.querySelectorAll('.phase').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(phaseId);
    if (target) target.classList.add('active');
}

function appendBusPacket(pkt) {
    const stream = document.getElementById('busStream');
    if (!stream) return;

    const div = document.createElement('div');
    div.className = 'bus-packet';
    div.innerHTML = `<span style="color: var(--neon-green)">${pkt.latency_ms.toFixed(3)}ms</span> <b style="color: var(--neon-crimson)">${pkt.source_agent}</b> ➔ <b>${pkt.target_agent}</b>: <span style="color: #94a3b8">${escapeHtml(pkt.content.substring(0, 50))}...</span>`;
    
    stream.prepend(div);
    if (stream.children.length > 50) {
        stream.removeChild(stream.lastChild);
    }
}

function updateTelemetry(telemetry) {
    if (!telemetry) return;
    const latEl = document.getElementById('ipcLatencyVal');
    if (latEl) {
        latEl.innerText = `${telemetry.average_latency_ms.toFixed(3)} ms`;
    }
    const badge = document.getElementById('packetCountBadge');
    if (badge) {
        badge.innerText = `${telemetry.total_messages} PKTS`;
    }
}

async function refreshGraphState() {
    try {
        const res = await fetch('/api/graph/state');
        const data = await res.json();
        if (graphVisualizer) graphVisualizer.updateGraphData(data);
        const countEl = document.getElementById('graphNodesCount');
        if (countEl) countEl.innerText = `${data.total_nodes} NODES | ${data.total_edges} EDGES`;
    } catch (e) {}
}

function setupEventListeners() {
    // Deploy Mission Button
    const deployBtn = document.getElementById('deployMissionBtn');
    if (deployBtn) {
        deployBtn.addEventListener('click', async () => {
            deployBtn.innerText = "DEPLOYING...";
            audioSynth.playAlertTone();
            await fetch('/api/swarm/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_scope: "10.0.0.0/16 Enterprise Grid" })
            });
            setTimeout(() => { deployBtn.innerText = "🚀 DEPLOY SWARM"; }, 1500);
        });
    }

    // Direct Command Send
    const sendBtn = document.getElementById('sendCommandBtn');
    const cmdInput = document.getElementById('commandInput');
    const agentSelect = document.getElementById('targetAgentSelect');

    const transmit = async () => {
        const text = cmdInput.value.trim();
        if (!text) return;
        audioSynth.playPacketChime();

        await fetch('/api/agent/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent: agentSelect.value, command: text })
        });
        cmdInput.value = '';
    };

    if (sendBtn) sendBtn.addEventListener('click', transmit);
    if (cmdInput) cmdInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') transmit(); });

    // Run Cypher Console
    const runCypherBtn = document.getElementById('runCypherBtn');
    const cypherInput = document.getElementById('cypherInput');
    const cypherOutput = document.getElementById('cypherOutput');

    if (runCypherBtn) {
        runCypherBtn.addEventListener('click', async () => {
            const query = cypherInput.value.trim();
            const res = await fetch('/api/cypher/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });
            const data = await res.json();
            cypherOutput.innerText = `[${data.execution_time_us}μs] ${data.summary || JSON.stringify(data.records || data)}`;
            refreshGraphState();
        });
    }

    // Audio SFX Toggle
    const audioBtn = document.getElementById('audioToggleBtn');
    if (audioBtn) {
        audioBtn.addEventListener('click', () => {
            audioSynth.enabled = !audioSynth.enabled;
            audioBtn.innerText = audioSynth.enabled ? "🔊 SFX ON" : "🔇 SFX OFF";
        });
    }

    // CRT FX Toggle
    const crtBtn = document.getElementById('scanlinesToggleBtn');
    if (crtBtn) {
        crtBtn.addEventListener('click', () => {
            document.body.classList.toggle('crt-overlay');
        });
    }
}

function taskAgent(agentName) {
    const select = document.getElementById('targetAgentSelect');
    const input = document.getElementById('commandInput');
    if (select) select.value = agentName;
    if (input) {
        input.focus();
        input.placeholder = `Directive for ${agentName}...`;
    }
}

function escapeHtml(str) {
    return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
