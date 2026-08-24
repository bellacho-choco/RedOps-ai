/**
 * REDOPS-AI Modern Interface Controller
 * Contemporary UI with smooth animations and real-time updates
 */

class ModernRedOpsUI {
    constructor() {
        this.ws = null;
        this.agents = {};
        this.graphCanvas = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initWebSocket();
        this.initGraph();
        this.startPerformanceUpdates();
        this.animateElements();
    }

    setupEventListeners() {
        // Deploy Mission Button
        document.getElementById('deployMissionBtn')?.addEventListener('click', () => {
            this.deployMission();
        });

        // Send Command Button
        document.getElementById('sendCommandBtn')?.addEventListener('click', () => {
            this.sendCommand();
        });

        // Command Input Enter Key
        document.getElementById('commandInput')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendCommand();
            }
        });

        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }

    initWebSocket() {
        try {
            this.ws = new WebSocket(`ws://${window.location.host}/ws/stream`);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.addLog('activityLog', 'WebSocket connection established', 'success');
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.addLog('activityLog', 'WebSocket connection error', 'error');
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.addLog('activityLog', 'WebSocket connection closed', 'warning');
                // Attempt reconnection after 5 seconds
                setTimeout(() => this.initWebSocket(), 5000);
            };
        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
        }
    }

    handleWebSocketMessage(data) {
        if (data.type === 'INITIAL_STATE') {
            this.agents = data.agents;
            this.updateAgentStates();
        } else if (data.type === 'AGENT_MESSAGE') {
            this.handleAgentMessage(data.data);
        } else if (data.type === 'TELEMETRY_HEARTBEAT') {
            this.updateTelemetry(data.telemetry);
        }
    }

    handleAgentMessage(message) {
        const agent = message.source_agent;
        const content = message.content;
        
        // Add to agent's terminal log
        const logContainer = document.getElementById(`logs-${agent}`);
        if (logContainer) {
            this.addLog(`logs-${agent}`, content, 'info');
        }

        // Add to activity log
        this.addLog('activityLog', `${agent}: ${content}`, 'info');
    }

    addLog(containerId, message, type = 'info') {
        const container = document.getElementById(containerId);
        if (!container) return;

        const entry = document.createElement('div');
        entry.className = 'log-entry animate-fade-in';
        
        const time = new Date().toLocaleTimeString();
        entry.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-message ${type}">${message}</span>
        `;

        container.appendChild(entry);
        container.scrollTop = container.scrollHeight;

        // Keep only last 50 entries
        while (container.children.length > 50) {
            container.removeChild(container.firstChild);
        }
    }

    updateAgentStates() {
        Object.keys(this.agents).forEach(agentName => {
            const agent = this.agents[agentName];
            const statusElement = document.querySelector(`[data-agent="${agentName}"] .agent-status`);
            if (statusElement) {
                statusElement.className = `agent-status ${agent.status.toLowerCase()}`;
                statusElement.textContent = `● ${agent.status}`;
            }
        });
    }

    updateTelemetry(telemetry) {
        // Update IPC latency
        const ipcElement = document.getElementById('ipcLatencyVal');
        if (ipcElement && telemetry.avg_latency_ms) {
            ipcElement.textContent = `${telemetry.avg_latency_ms.toFixed(3)} ms`;
        }

        // Update packet count
        const packetElement = document.getElementById('packetCountBadge');
        if (packetElement && telemetry.total_messages) {
            packetElement.textContent = `${telemetry.total_messages} PKTS`;
        }
    }

    initGraph() {
        const canvas = document.getElementById('attackGraphCanvas');
        if (!canvas) return;

        this.graphCanvas = canvas;
        const ctx = canvas.getContext('2d');
        
        // Set canvas size
        const resizeCanvas = () => {
            canvas.width = canvas.parentElement.clientWidth;
            canvas.height = canvas.parentElement.clientHeight;
            this.drawGraph();
        };
        
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
    }

    drawGraph() {
        if (!this.graphCanvas) return;
        
        const ctx = this.graphCanvas.getContext('2d');
        const width = this.graphCanvas.width;
        const height = this.graphCanvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        // Draw sample nodes (in real implementation, this would come from server)
        const nodes = [
            { x: width * 0.2, y: height * 0.5, label: 'Internet', type: 'clean' },
            { x: width * 0.4, y: height * 0.3, label: 'DMZ', type: 'discovered' },
            { x: width * 0.4, y: height * 0.7, label: 'Web Server', type: 'discovered' },
            { x: width * 0.6, y: height * 0.5, label: 'Database', type: 'compromised' },
            { x: width * 0.8, y: height * 0.5, label: 'Crown Jewel', type: 'crown' }
        ];

        const edges = [
            [0, 1], [0, 2], [1, 3], [2, 3], [3, 4]
        ];

        // Draw edges
        ctx.strokeStyle = 'rgba(99, 102, 241, 0.3)';
        ctx.lineWidth = 2;
        edges.forEach(([from, to]) => {
            ctx.beginPath();
            ctx.moveTo(nodes[from].x, nodes[from].y);
            ctx.lineTo(nodes[to].x, nodes[to].y);
            ctx.stroke();
        });

        // Draw nodes
        nodes.forEach(node => {
            const colors = {
                clean: '#64748b',
                discovered: '#06b6d4',
                compromised: '#ef4444',
                crown: '#f59e0b'
            };

            ctx.beginPath();
            ctx.arc(node.x, node.y, 20, 0, Math.PI * 2);
            ctx.fillStyle = colors[node.type];
            ctx.fill();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw label
            ctx.fillStyle = '#f8fafc';
            ctx.font = '12px Inter';
            ctx.textAlign = 'center';
            ctx.fillText(node.label, node.x, node.y + 35);
        });
    }

    startPerformanceUpdates() {
        // Update performance metrics every 2 seconds
        setInterval(() => {
            this.updatePerformanceMetrics();
        }, 2000);
    }

    updatePerformanceMetrics() {
        // Simulate performance data (in real implementation, fetch from API)
        const cpu = Math.floor(Math.random() * 30) + 20;
        const memory = Math.floor(Math.random() * 20) + 50;
        const network = Math.floor(Math.random() * 15) + 5;

        const updateProgressBar = (selector, value) => {
            const bar = document.querySelector(selector);
            if (bar) {
                bar.style.width = `${value}%`;
            }
        };

        updateProgressBar('.progress-bar:nth-child(1) .progress-fill', cpu);
        updateProgressBar('.progress-bar:nth-child(2) .progress-fill', memory);
        updateProgressBar('.progress-bar:nth-child(3) .progress-fill', network);
    }

    animateElements() {
        // Add staggered animation to cards
        const cards = document.querySelectorAll('.agent-card, .sidebar-section');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            card.classList.add('animate-fade-in');
        });
    }

    async deployMission() {
        const target = prompt('Enter target IP or domain:', '127.0.0.1');
        if (!target) return;

        this.addLog('activityLog', `Deploying mission to ${target}...`, 'info');

        try {
            const response = await fetch('/api/swarm/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_scope: target })
            });

            const result = await response.json();
            this.addLog('activityLog', `Mission deployed: ${result.message}`, 'success');
        } catch (error) {
            this.addLog('activityLog', `Mission deployment failed: ${error.message}`, 'error');
        }
    }

    async sendCommand() {
        const agentSelect = document.getElementById('targetAgentSelect');
        const commandInput = document.getElementById('commandInput');
        
        const agent = agentSelect.value;
        const command = commandInput.value.trim();
        
        if (!command) return;

        this.addLog('activityLog', `Sending command to ${agent}: ${command}`, 'info');

        try {
            const response = await fetch('/api/agent/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ agent, command })
            });

            const result = await response.json();
            this.addLog(`logs-${agent}`, result.result || result.message, 'success');
            commandInput.value = '';
        } catch (error) {
            this.addLog('activityLog', `Command failed: ${error.message}`, 'error');
        }
    }

    taskAgent(agentName) {
        const command = prompt(`Enter directive for ${agentName}:`, 'status check');
        if (command) {
            document.getElementById('targetAgentSelect').value = agentName;
            document.getElementById('commandInput').value = command;
            this.sendCommand();
        }
    }
}

// Quick action functions
function runScan() {
    const target = prompt('Enter target for scan:', '127.0.0.1');
    if (target) {
        console.log(`Starting scan on ${target}`);
        // Implement scan logic
    }
}

function runAudit() {
    const url = prompt('Enter URL for security audit:', 'https://example.com');
    if (url) {
        console.log(`Starting audit on ${url}`);
        // Implement audit logic
    }
}

function viewGraph() {
    console.log('Opening graph view');
    // Implement graph view logic
}

function generateReport() {
    console.log('Generating security report');
    // Implement report generation logic
}

// Initialize the UI when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.modernUI = new ModernRedOpsUI();
});