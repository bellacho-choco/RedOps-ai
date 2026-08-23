/**
 * REDOPS-AI - Holographic Attack Graph Canvas Visualizer
 * Real-time dynamic particle graph rendering, node pulse rings, lateral movement animation
 */

class AttackGraphVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.nodes = [];
        this.edges = [];
        this.particles = [];
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.animate();
    }

    resize() {
        if (!this.canvas) return;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    updateGraphData(graphState) {
        if (!graphState || !graphState.nodes) return;
        
        const w = this.canvas.width;
        const h = this.canvas.height;
        const count = graphState.nodes.length;

        // Position nodes in an orbital circular layout
        this.nodes = graphState.nodes.map((n, i) => {
            const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
            const rx = w * 0.38;
            const ry = h * 0.35;
            const x = w / 2 + Math.cos(angle) * rx;
            const y = h / 2 + Math.sin(angle) * ry;
            
            return {
                id: n.id,
                labels: n.labels,
                properties: n.properties || {},
                x: x,
                y: y,
                pulse: 0
            };
        });

        this.edges = graphState.edges || [];
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (!this.ctx) return;

        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Draw Edges
        ctx.lineWidth = 1.5;
        this.edges.forEach(edge => {
            const src = this.nodes.find(n => n.id === edge.source);
            const tgt = this.nodes.find(n => n.id === edge.target);
            if (src && tgt) {
                ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
                ctx.beginPath();
                ctx.moveTo(src.x, src.y);
                ctx.lineTo(tgt.x, tgt.y);
                ctx.stroke();
            }
        });

        // Draw Nodes
        this.nodes.forEach(node => {
            const status = node.properties.status || 'CLEAN';
            let color = '#64748b';
            let glow = 'rgba(100, 116, 139, 0.4)';

            if (status === 'DISCOVERED') {
                color = '#00f0ff';
                glow = 'rgba(0, 240, 255, 0.8)';
            } else if (status === 'COMPROMISED') {
                color = '#ff0055';
                glow = 'rgba(255, 0, 85, 0.9)';
            } else if (status === 'CROWN_JEWEL_ACCESSED' || node.labels.includes('CrownJewel')) {
                color = '#ffd700';
                glow = 'rgba(255, 215, 0, 0.9)';
            }

            // Outer Pulse Ring
            node.pulse = (node.pulse + 0.05) % (Math.PI * 2);
            const pulseRadius = 9 + Math.sin(node.pulse) * 3;

            ctx.shadowBlur = 12;
            ctx.shadowColor = glow;

            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, 6, 0, Math.PI * 2);
            ctx.fill();

            // Ring
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(node.x, node.y, pulseRadius, 0, Math.PI * 2);
            ctx.stroke();

            // Reset shadow
            ctx.shadowBlur = 0;

            // Label
            ctx.font = '9px "JetBrains Mono"';
            ctx.fillStyle = '#e2e8f0';
            ctx.textAlign = 'center';
            ctx.fillText(node.id.substring(0, 14), node.x, node.y + 18);
        });
    }
}
