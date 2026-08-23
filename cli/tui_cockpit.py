"""
====================================================================
PROJECT REDOPS-AI - 6-AGENT SPLIT TERMINAL TUI COCKPIT
Full-Screen Multi-Agent Live Terminal Dashboard in Pure Python / Rich
====================================================================
"""

import asyncio
import time
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from backend.agents import swarm_matrix
from backend.cypher_engine import graph_engine
from backend.swarm_bus import swarm_bus
from backend.llm_provider import llm_provider


def make_agent_panel(agent_name: str) -> Panel:
    agent = swarm_matrix.get_agent(agent_name)
    if not agent:
        return Panel("Offline", title=agent_name)

    logs = agent.terminal_logs[-7:]
    content = []
    for l in logs:
        content.append(f"[dim]{l['timestamp']}[/dim] [bold white]{l['text']}[/bold white]")

    body_text = "\n".join(content) if content else "[dim]Awaiting tactical directive...[/dim]"
    
    border_color = agent.color_hex
    stat_style = "bold green" if agent.status == "IDLE" else "bold red flash"

    title = f"[{border_color}]● {agent.codename}[/{border_color}] [{stat_style}][{agent.status}][/{stat_style}]"
    return Panel(
        body_text,
        title=title,
        subtitle=f"[dim]{agent.specialization[:40]}[/dim]",
        border_style=border_color
    )


def generate_cockpit_layout() -> Layout:
    layout = Layout()

    # Split into Header, Main Body (2 columns of 3 agents), and Footer
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )

    # Header
    llm_stat = llm_provider.get_status()
    telemetry = swarm_bus.get_telemetry()
    header_table = Table.grid(expand=True)
    header_table.add_column(justify="left", ratio=1)
    header_table.add_column(justify="center", ratio=2)
    header_table.add_column(justify="right", ratio=1)

    header_table.add_row(
        "[bold red]⚡ REDOPS-AI[/bold red] [dim]TUI COMMAND MATRIX[/dim]",
        f"[bold yellow]LLM:[/bold yellow] [cyan]{llm_stat['provider'].upper()}[/cyan] ({llm_stat['model']}) | [bold green]IPC:[/bold green] [white]{telemetry.get('avg_latency_ms', 0):.3f}ms[/white]",
        f"[bold cyan]Total Packets:[/bold cyan] {telemetry.get('total_messages', 0)} | [dim]Press Ctrl+C to exit TUI[/dim]"
    )
    layout["header"].update(Panel(header_table, style="bold red"))

    # Body with 2 columns
    layout["body"].split_row(
        Layout(name="left_column", ratio=1),
        Layout(name="right_column", ratio=1)
    )

    layout["left_column"].split_column(
        Layout(name="overlord", ratio=1),
        Layout(name="spectre", ratio=1),
        Layout(name="nexus", ratio=1)
    )

    layout["right_column"].split_column(
        Layout(name="vortex", ratio=1),
        Layout(name="cipher", ratio=1),
        Layout(name="chrono", ratio=1)
    )

    layout["overlord"].update(make_agent_panel("OVERLORD-PRIME"))
    layout["spectre"].update(make_agent_panel("SPECTRE-RECON"))
    layout["nexus"].update(make_agent_panel("NEXUS-CYPHER"))
    layout["vortex"].update(make_agent_panel("VORTEX-EXPLOIT"))
    layout["cipher"].update(make_agent_panel("CIPHER-MORPH"))
    layout["chrono"].update(make_agent_panel("CHRONO-DEBRIEF"))

    # Footer
    layout["footer"].update(Panel("[bold yellow]Status:[/] Swarm live in memory. Type commands in terminal REPL.", style="dim"))
    return layout


async def run_live_tui(duration_seconds: int = 30):
    console = Console()
    console.print("[bold green]Starting live 6-agent split cockpit...[/bold green]")
    
    with Live(generate_cockpit_layout(), refresh_per_second=4, console=console) as live:
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            live.update(generate_cockpit_layout())
            await asyncio.sleep(0.25)
