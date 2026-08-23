"""
====================================================================
PROJECT REDOPS-AI - TERMINAL TUI MULTI-AGENT COCKPIT
Rich & Prompt-Toolkit Powered 6-Hero Split Terminal RedOps Matrix
====================================================================
"""

import sys
import os
import time
import asyncio
import threading
from typing import Dict, List, Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.live import Live
from rich.syntax import Syntax
from rich import box

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.swarm_bus import swarm_bus, AgentMessage
from backend.agents import swarm_matrix
from backend.cypher_engine import graph_engine
from cython_core.fast_entropy import is_cython_accelerated, calculate_shannon_entropy


console = Console()


def create_header() -> Panel:
    """Creates the RedOps-AI Neural Matrix Header"""
    accel = "CYTHON [C-SPEED ACTIVE]" if is_cython_accelerated() else "CYTHON [PURE-PY ACCELERATED]"
    
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=2)
    grid.add_column(justify="right", ratio=1)

    grid.add_row(
        Text("⚡ REDOPS-AI", style="bold red"),
        Text("🤖 6-AGENT HERO TERMINAL MATRIX | SUB-MS IPC BUS", style="bold cyan"),
        Text(f"⚙️ {accel} | 🚀 IPC: <0.1ms", style="bold yellow")
    )
    return Panel(grid, style="bold red", box=box.HEAVY)


def render_agent_panel(hero) -> Panel:
    """Renders an individual agent's dedicated streaming terminal pane"""
    status_style = "bold green" if hero.status == "IDLE" else "bold yellow blink"
    if hero.status == "EXECUTING" or hero.status == "MUTATING":
        status_style = "bold red blink"

    title = f"[{hero.color_hex}]{hero.codename}[/] [white]|[/] [{status_style}]{hero.status}[/]"
    
    # Get last 5 log lines for this agent
    lines = []
    for log in hero.terminal_logs[-5:]:
        t = log.get("timestamp", "")
        txt = log.get("text", "")
        lvl = log.get("level", "INFO")
        lines.append(f"[dim]{t}[/] [cyan]{lvl}[/] {txt}")
    
    body = "\n".join(lines) if lines else "[dim italic]Terminal idle. Awaiting tactical stream...[/]"
    
    return Panel(
        body,
        title=title,
        subtitle=f"[dim]{hero.role} - {hero.specialization[:35]}...[/]",
        border_style=hero.color_hex,
        box=box.ROUNDED,
        height=9
    )


def create_cypher_graph_panel() -> Panel:
    """Renders real-time Cypher Attack Graph Topology in ASCII/ANSI format"""
    table = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True, header_style="bold magenta")
    table.add_column("Node ID", style="cyan", width=18)
    table.add_column("Zone", style="yellow", width=14)
    table.add_column("Service/CVE", style="white")
    table.add_column("Status", justify="right")

    for node in list(graph_engine.nodes.values())[:6]:
        props = node.properties
        status = props.get("status", "CLEAN")
        style = "green"
        if status == "DISCOVERED":
            style = "cyan"
        elif status == "COMPROMISED":
            style = "bold red"
        elif status == "CROWN_JEWEL_ACCESSED":
            style = "bold gold1 blink"

        table.add_row(
            node.id,
            props.get("zone", "INTERNAL"),
            props.get("service", props.get("cve_id", "Node")),
            f"[{style}]{status}[/]"
        )

    return Panel(table, title="🧬 [bold green]CYPHER ATTACK GRAPH TOPOLOGY[/]", box=box.ROUNDED)


def create_ipc_stream_panel() -> Panel:
    """Renders the real-time sub-millisecond Inter-Agent IPC Telemetry feed"""
    telemetry = swarm_bus.get_telemetry()
    lines = []
    
    for msg in list(swarm_bus.history)[-5:]:
        src = msg.source_agent
        tgt = msg.target_agent
        evt = msg.event_type
        lat = msg.latency_ms
        lines.append(f"[yellow]{msg.message_id}[/] [bold cyan]{src}[/] ➔ [bold magenta]{tgt}[/] [dim]({evt})[/] [bold green]{lat:.3f}ms[/]\n  [white]{msg.content[:70]}[/]")

    content = "\n".join(lines) if lines else "[dim]No IPC packets in buffer. Sub-ms bus listening...[/]"
    
    sub = f"Avg Latency: [bold green]{telemetry['average_latency_ms']}ms[/] | Packets: [bold cyan]{telemetry['total_messages']}[/]"
    return Panel(content, title="📡 [bold yellow]SUB-MS INTER-AGENT IPC FEED[/]", subtitle=sub, box=box.ROUNDED)


def make_layout() -> Layout:
    """Constructs the responsive multi-panel terminal grid layout"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )

    layout["body"].split_row(
        Layout(name="agents_grid", ratio=3),
        Layout(name="sidebar", ratio=2)
    )

    # 6 Agent Hero Terminal Grid (3 rows x 2 cols)
    layout["agents_grid"].split_column(
        Layout(name="row1"),
        Layout(name="row2"),
        Layout(name="row3")
    )
    layout["agents_grid"]["row1"].split_row(Layout(name="hero1"), Layout(name="hero2"))
    layout["agents_grid"]["row2"].split_row(Layout(name="hero3"), Layout(name="hero4"))
    layout["agents_grid"]["row3"].split_row(Layout(name="hero5"), Layout(name="hero6"))

    # Sidebar: Cypher Graph + Sub-ms IPC
    layout["sidebar"].split_column(
        Layout(name="cypher_graph", ratio=1),
        Layout(name="ipc_feed", ratio=1)
    )

    return layout


def update_layout(layout: Layout):
    """Updates the layout with live streaming agent data"""
    layout["header"].update(create_header())
    
    heroes = swarm_matrix.heroes
    layout["agents_grid"]["row1"]["hero1"].update(render_agent_panel(heroes["OVERLORD-PRIME"]))
    layout["agents_grid"]["row1"]["hero2"].update(render_agent_panel(heroes["SPECTRE-RECON"]))
    layout["agents_grid"]["row2"]["hero3"].update(render_agent_panel(heroes["NEXUS-CYPHER"]))
    layout["agents_grid"]["row2"]["hero4"].update(render_agent_panel(heroes["VORTEX-EXPLOIT"]))
    layout["agents_grid"]["row3"]["hero5"].update(render_agent_panel(heroes["CIPHER-MORPH"]))
    layout["agents_grid"]["row3"]["hero6"].update(render_agent_panel(heroes["CHRONO-DEBRIEF"]))

    layout["sidebar"]["cypher_graph"].update(create_cypher_graph_panel())
    layout["sidebar"]["ipc_feed"].update(create_ipc_stream_panel())

    footer_text = Text.from_markup(
        "[bold white on red] COMMAND DIRECTIVES [/] [bold cyan]Press [Y] Deploy Autonomous Swarm | [Q] Run Cypher Query | [E] Shannon Entropy Test | [Ctrl+C] Exit[/]"
    )
    layout["footer"].update(Panel(footer_text, box=box.HORIZONTALS))


async def run_terminal_cockpit():
    """Main async terminal execution loop with rich Live rendering"""
    layout = make_layout()
    
    console.clear()
    console.print("[bold red]INITIALIZING REDOPS-AI TERMINAL MATRIX...[/]")
    time.sleep(0.5)

    # Launch autonomous swarm demo in background after 1 second
    asyncio.create_task(demo_runner())

    with Live(layout, refresh_per_second=8, screen=True) as live:
        try:
            while True:
                update_layout(layout)
                await asyncio.sleep(0.125)
        except KeyboardInterrupt:
            pass


async def demo_runner():
    """Triggers autonomous multi-agent operation for live terminal demonstration"""
    await asyncio.sleep(1.0)
    await swarm_matrix.start_autonomous_operation("10.0.0.0/16 Enterprise Grid")


def main():
    try:
        asyncio.run(run_terminal_cockpit())
    except KeyboardInterrupt:
        console.print("\n[bold red]REDOPS-AI TERMINAL MATRIX SHUT DOWN.[/]")


if __name__ == "__main__":
    main()
