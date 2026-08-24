"""
====================================================================
PROJECT REDOPS-AI - MODERN REDESIGNED CLI
Contemporary Interface with Enhanced UX and Visual Design
====================================================================
"""

import sys
import os
import asyncio
import time
from typing import Optional, Dict, Any

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich import box
from rich.text import Text
from rich.align import Align

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.swarm_bus import swarm_bus, AgentMessage
from backend.agents import swarm_matrix
from backend.cypher_engine import graph_engine
from backend.llm_provider import llm_provider
from backend.live_scanner import socket_scanner, web_auditor, dns_auditor
from backend.sast_analyzer import sast_auditor
from backend.skills_engine import skills_engine
from cython_core.fast_entropy import calculate_shannon_entropy, polymorphic_mutation_sim, is_cython_accelerated
from cli.tui_cockpit import run_live_tui

# Modern color scheme
class Colors:
    PRIMARY = "#6366f1"
    SECONDARY = "#8b5cf6"
    ACCENT = "#06b6d4"
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    DANGER = "#ef4444"
    DARK = "#0f172a"
    CARD = "#1e293b"
    TEXT_PRIMARY = "#f8fafc"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_MUTED = "#64748b"

console = Console()


class ModernCLI:
    def __init__(self):
        self.console = Console()
        self.current_context = "main"
        self.history = []
        
    def print_banner(self):
        """Display modern animated banner"""
        accel = "CYTHON [C-SPEED]" if is_cython_accelerated() else "CYTHON [PURE-PY]"
        llm_stat = llm_provider.get_status()
        
        banner = Panel(
            f"""
[bold {Colors.PRIMARY}]╔════════════════════════════════════════════════════════════════╗[/bold {Colors.PRIMARY}]
[bold {Colors.PRIMARY}]║[/bold {Colors.PRIMARY}]  [bold white]REDOPS-AI[/bold white] [dim]| Modern Security Operations Center [dim]  [bold {Colors.PRIMARY}]║[/bold {Colors.PRIMARY}]
[bold {Colors.PRIMARY}]╚════════════════════════════════════════════════════════════════╝[/bold {Colors.PRIMARY}]

[dim]┌─────────────────────────────────────────────────────────────────────┐[/dim]
[dim]│[/dim] [bold {Colors.ACCENT}]⚡ Autonomous Multi-Agent Security Platform[/bold {Colors.ACCENT}] [dim]│[/dim]
[dim]│[/dim] [dim]Engine: Live Sockets & Real SAST | Acceleration: {accel}[/dim] [dim]│[/dim]
[dim]│[/dim] [dim]LLM: {llm_stat['provider'].upper()} ({llm_stat['model']}) | Mode: {llm_stat['active_mode']}[/dim] [dim]│[/dim]
[dim]└─────────────────────────────────────────────────────────────────────┘[/dim]
""",
            border_style=Colors.PRIMARY,
            padding=(1, 2)
        )
        self.console.print(banner)

    def print_help(self):
        """Display modern help menu"""
        table = Table(
            title="[bold yellow]📋 Available Commands[/bold yellow]",
            box=box.ROUNDED,
            header_style=f"bold {Colors.ACCENT}",
            border_style=Colors.TEXT_MUTED
        )
        table.add_column("Command", style=f"bold {Colors.PRIMARY}", width=20)
        table.add_column("Description", style=Colors.TEXT_PRIMARY)
        table.add_column("Example", style=Colors.TEXT_SECONDARY, width=25)

        commands = [
            ("chat [msg]", "AI-powered security assistance", "chat check port 80"),
            ("agent <name> <cmd>", "Direct agent communication", "agent spectre scan 192.168.1.1"),
            ("mission <target>", "Deploy full swarm assessment", "mission example.com"),
            ("scan <target>", "TCP port scanning", "scan 192.168.1.1"),
            ("audit <url>", "Web security audit", "audit https://example.com"),
            ("entropy <target>", "Shannon entropy analysis", "entropy password.txt"),
            ("graph", "Display attack topology", "graph"),
            ("status", "Agent status overview", "status"),
            ("skills [query]", "Search security playbooks", "skills sqli"),
            ("tui [duration]", "Launch visual dashboard", "tui 30"),
            ("monitor", "System performance metrics", "monitor"),
            ("clear", "Clear terminal", "clear"),
            ("exit", "Exit RedOps-AI", "exit"),
        ]

        for cmd, desc, example in commands:
            table.add_row(cmd, desc, f"[dim]{example}[/dim]")

        self.console.print(table)

    def print_status_overview(self):
        """Display modern status dashboard"""
        statuses = swarm_matrix.get_all_status()
        telemetry = swarm_bus.get_telemetry()
        
        # Main status table
        table = Table(
            title="[bold cyan]📊 System Status Overview[/bold cyan]",
            box=box.ROUNDED,
            show_header=True,
            header_style=f"bold {Colors.ACCENT}",
            border_style=Colors.TEXT_MUTED
        )
        table.add_column("Agent", style=f"bold {Colors.PRIMARY}", width=18)
        table.add_column("Role", style=Colors.TEXT_PRIMARY, width=25)
        table.add_column("Status", width=12)
        table.add_column("Activity", style=Colors.TEXT_SECONDARY)

        for name, data in statuses.items():
            status_emoji = "🟢" if data["status"] == "IDLE" else "🔴" if data["status"] == "ERROR" else "🟡"
            status_style = f"bold {Colors.SUCCESS}" if data["status"] == "IDLE" else f"bold {Colors.DANGER}"
            
            table.add_row(
                name,
                data["role"],
                f"{status_emoji} [{status_style}]{data['status']}[/{status_style}]",
                data["latest_log"][:40] + "..." if len(data["latest_log"]) > 40 else data["latest_log"]
            )

        self.console.print(table)
        
        # Performance metrics
        metrics_table = Table(box=box.SIMPLE, show_header=False, padding=0)
        metrics_table.add_column("Metric", style=Colors.TEXT_SECONDARY)
        metrics_table.add_column("Value", style=f"bold {Colors.ACCENT}")
        
        metrics_table.add_row("IPC Latency", f"{telemetry.get('avg_latency_ms', 0):.3f}ms")
        metrics_table.add_row("Total Messages", str(telemetry.get('total_messages', 0)))
        metrics_table.add_row("Graph Nodes", str(len(graph_engine.nodes)))
        metrics_table.add_row("Graph Edges", str(len(graph_engine.edges)))
        
        self.console.print(Panel(
            metrics_table,
            title="[dim]📈 Performance Metrics[/dim]",
            border_style=Colors.TEXT_MUTED
        ))

    async def handle_command(self, cmd_str: str):
        """Process user commands with modern feedback"""
        parts = cmd_str.strip().split()
        if not parts or not parts[0]:
            return

        action = parts[0].lower()

        if action == "help":
            self.print_help()

        elif action == "chat":
            await self.handle_chat_command(cmd_str)

        elif action == "agent":
            await self.handle_agent_command(parts)

        elif action == "mission":
            await self.handle_mission_command(parts)

        elif action == "scan":
            await self.handle_scan_command(parts)

        elif action == "audit":
            await self.handle_audit_command(parts)

        elif action == "entropy":
            await self.handle_entropy_command(parts)

        elif action == "graph":
            self.console.print(graph_engine.render_ascii_graph())

        elif action == "status":
            self.print_status_overview()

        elif action == "skills":
            await self.handle_skills_command(parts)

        elif action == "tui":
            duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
            await run_live_tui(duration)

        elif action == "monitor":
            await self.handle_monitor_command()

        elif action == "clear":
            self.console.clear()
            self.print_banner()

        elif action in ["exit", "quit"]:
            self.console.print(f"[{Colors.DANGER}]👋 Shutting down RedOps-AI...[/]")
            sys.exit(0)

        else:
            self.console.print(f"[{Colors.DANGER}]❌ Unknown command: '{parts[0]}'[/]")
            self.console.print(f"[dim]Type 'help' for available commands[/]")

    async def handle_chat_command(self, cmd_str):
        """Handle AI chat interactions"""
        parts = cmd_str.strip().split()
        user_msg = " ".join(parts[1:]) if len(parts) > 1 else ""
        
        if user_msg:
            # Single message
            self.console.print(f"\n[{Colors.ACCENT}]💬 You:[/] {user_msg}")
            
            with Progress(
                SpinnerColumn(style=Colors.PRIMARY),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task("[bold yellow]🧠 Processing your request...", total=None)
                
                ctx = {"target": "Active Workspace", "graph_nodes": len(graph_engine.nodes)}
                reply = await llm_provider.generate_cyber_reasoning("REDOPS-AI Commander", user_msg, ctx)
            
            self.console.print(f"\n[{Colors.PRIMARY}]🤖 REDOPS-AI:[/]")
            self.console.print(Markdown(reply))
        else:
            # Interactive chat mode
            self.console.print(f"\n[{Colors.SECONDARY}]═══════════════════════════════════════════════════════════════[/]")
            self.console.print(f"[{Colors.SECONDARY}]💬 INTERACTIVE CHAT MODE[/]")
            self.console.print(f"[dim]Ask security questions, request advice, or issue commands.[/]")
            self.console.print(f"[dim]Type 'exit' to return to main menu.[/]")
            self.console.print(f"[{Colors.SECONDARY}]═══════════════════════════════════════════════════════════════[/]\n")
            
            while True:
                try:
                    chat_input = Prompt.ask(
                        f"[{Colors.PRIMARY}]REDOPS-CHAT[/] > ",
                        default="",
                        show_default=False
                    )
                    
                    if not chat_input.strip():
                        continue
                    if chat_input.lower() in ["exit", "back", "quit"]:
                        self.console.print("[dim]Exiting chat mode[/]")
                        break
                    
                    self.console.print(f"\n[{Colors.ACCENT}]💬 You:[/] {chat_input}")
                    
                    with Progress(
                        SpinnerColumn(style=Colors.PRIMARY),
                        TextColumn("[progress.description]{task.description}"),
                        transient=True,
                    ) as progress:
                        task = progress.add_task("[bold yellow]🧠 Analyzing...", total=None)
                        ctx = {"target": "Active Workspace", "graph_nodes": len(graph_engine.nodes)}
                        reply = await llm_provider.generate_cyber_reasoning("REDOPS-AI", chat_input, ctx)
                    
                    self.console.print(f"\n[{Colors.PRIMARY}]🤖 REDOPS-AI:[/]")
                    self.console.print(Markdown(reply))
                    self.console.print()
                    
                except (KeyboardInterrupt, EOFError):
                    self.console.print("\n[dim]Chat mode interrupted[/]")
                    break

    async def handle_agent_command(self, parts):
        """Handle direct agent communication"""
        if len(parts) < 3:
            self.console.print(f"[{Colors.DANGER}]❌ Usage: agent <NAME> <command>[/]")
            self.console.print(f"[dim]Available: OVERLORD-PRIME, SPECTRE-RECON, NEXUS-CYPHER, VORTEX-EXPLOIT, CIPHER-MORPH, CHRONO-DEBRIEF[/]")
            return

        agent_name = parts[1].upper()
        agent = swarm_matrix.get_agent(agent_name)
        
        if not agent:
            self.console.print(f"[{Colors.DANGER}]❌ Agent '{agent_name}' not found[/]")
            return

        directive = " ".join(parts[2:])
        self.console.print(f"[{Colors.ACCENT}]📡 Sending to [{agent.color_hex}]{agent_name}[/{agent.color_hex}]:[/] {directive}")
        
        with Progress(
            SpinnerColumn(style=Colors.SUCCESS),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(f"[bold cyan]⚡ {agent_name} processing...", total=None)
            response = await agent.process_task(directive)
        
        self.console.print(f"\n[{agent.color_hex}]● {agent_name} Response:[/{agent.color_hex}]")
        self.console.print(Markdown(response) if "\n" in response else response)

    async def handle_mission_command(self, parts):
        """Handle mission deployment"""
        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        
        self.console.print(f"\n[{Colors.PRIMARY}]🚀 DEPLOYING AUTONOMOUS SWARM[/]")
        self.console.print(f"[dim]Target: [white]{target}[/white][/]")
        
        with Progress(
            SpinnerColumn(style=Colors.PRIMARY),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(style=Colors.PRIMARY),
            TimeElapsedColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("[bold yellow]🔍 Executing multi-phase assessment...", total=100)
            result = await swarm_matrix.overlord.execute_mission(target)
        
        self.console.print(f"\n[{Colors.SUCCESS}]✅ MISSION COMPLETED[/]")
        
        # Results table
        results_table = Table(box=box.ROUNDED, show_header=True)
        results_table.add_column("Metric", style=Colors.TEXT_SECONDARY)
        results_table.add_column("Value", style=f"bold {Colors.ACCENT}")
        
        results_table.add_row("Target IP", str(result['scan_data'].get('ip', 'N/A')))
        results_table.add_row("Open Ports", str(result['scan_data'].get('open_ports_count', 0)))
        results_table.add_row("Scan Duration", f"{result['scan_data'].get('scan_duration_s', 0)}s")
        results_table.add_row("Vulnerabilities", str(len(result.get('vuln_data', {}).get('security_risks', []))))
        
        self.console.print(results_table)
        
        if result.get("report"):
            self.console.print(f"\n[{Colors.WARNING}]📋 EXECUTIVE REPORT[/]")
            self.console.print(Markdown(result["report"][:500]))

    async def handle_scan_command(self, parts):
        """Handle port scanning"""
        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        
        self.console.print(f"[{Colors.ACCENT}]🔍 Scanning {target}...[/]")
        
        with Progress(
            SpinnerColumn(style=Colors.SUCCESS),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("[bold cyan]Probing ports...", total=None)
            res = await socket_scanner.scan_target(target)
        
        if res.get("open_ports"):
            table = Table(
                title=f"[{Colors.SUCCESS}]🎯 SCAN RESULTS: {res['target']}[/]",
                box=box.ROUNDED
            )
            table.add_column("Port", style=f"bold {Colors.PRIMARY}")
            table.add_column("Service", style=Colors.TEXT_PRIMARY)
            table.add_column("Latency", style=Colors.ACCENT)
            table.add_column("Banner", style=Colors.TEXT_SECONDARY)
            
            for p in res["open_ports"]:
                table.add_row(
                    str(p["port"]),
                    p["service"],
                    f"{p['latency_ms']}ms",
                    p["banner"][:30] + "..." if len(p["banner"]) > 30 else p["banner"]
                )
            
            self.console.print(table)
        else:
            self.console.print(f"[{Colors.WARNING}]⚠️ No open ports found[/]")
        
        self.console.print(f"[dim]Scanned {res['total_probed']} ports in {res['scan_duration_s']}s[/]")
        
        # Ingest into graph
        graph_engine.ingest_live_scan(res)

    async def handle_audit_command(self, parts):
        """Handle web security audit"""
        url = parts[1] if len(parts) > 1 else "https://example.com"
        
        self.console.print(f"[{Colors.ACCENT}]🌐 Auditing {url}...[/]")
        
        with Progress(
            SpinnerColumn(style=Colors.SUCCESS),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("[bold cyan]Analyzing security posture...", total=None)
            res = await web_auditor.audit_url(url)
        
        self.console.print(f"[{Colors.SUCCESS}]✅ Audit Complete[/]")
        self.console.print(f"Status: [bold green]{res.get('status_code')}[/bold green]")
        
        if res.get("security_risks"):
            risk_table = Table(title=f"[{Colors.DANGER}]⚠️ SECURITY RISKS[/]", box=box.ROUNDED)
            risk_table.add_column("Severity", style=Colors.DANGER)
            risk_table.add_column("Issue", style=Colors.TEXT_PRIMARY)
            
            for risk in res["security_risks"]:
                risk_table.add_row(risk["severity"], risk["title"])
            
            self.console.print(risk_table)

    async def handle_entropy_command(self, parts):
        """Handle entropy analysis"""
        target = parts[1] if len(parts) > 1 else ""
        if not target:
            self.console.print(f"[{Colors.DANGER}]❌ Usage: entropy <file_or_text>[/]")
            return

        if os.path.exists(target):
            self.console.print(f"[{Colors.ACCENT}]🧬 Analyzing: {target}[/]")
            if os.path.isdir(target):
                res = sast_auditor.analyze_directory(target)
                self.console.print(f"Files: {res['files_scanned']} | Findings: {res['vulnerable_files_count']}")
            else:
                res = sast_auditor.analyze_file(target)
                self.console.print(f"Findings: {res['total_findings']}")
        else:
            ent = calculate_shannon_entropy(target.encode('utf-8'))
            findings = sast_auditor.analyze_buffer(target, "input")
            self.console.print(f"Entropy: [bold yellow]{ent:.4f}[/bold yellow] | Patterns: [bold cyan]{len(findings)}[/bold cyan]")

    async def handle_skills_command(self, parts):
        """Handle skills search"""
        query = parts[1] if len(parts) > 1 else ""
        
        if query:
            results = skills_engine.search_skills(query, limit=10)
            table = Table(title=f"[{Colors.ACCENT}]🔍 Skills: '{query}'[/]", box=box.ROUNDED)
            table.add_column("Name", style=f"bold {Colors.PRIMARY}")
            table.add_column("Category", style=Colors.TEXT_SECONDARY)
            table.add_column("Description", style=Colors.TEXT_PRIMARY)
            
            for skill in results:
                table.add_row(skill["name"], skill["category"], skill["description"][:40] + "...")
            
            self.console.print(table)
        else:
            summary = skills_engine.get_summary()
            self.console.print(f"[{Colors.ACCENT}]📚 Total Skills: [bold white]{summary['total_skills']}[/bold white][/]")
            
            for cat, count in summary["categories"].items():
                self.console.print(f"  [dim]•[/] [bold yellow]{cat}:[/bold yellow] {count}")

    async def handle_monitor_command(self):
        """Display system monitoring dashboard"""
        from backend.monitoring import monitoring_system
        
        self.console.print(f"[{Colors.ACCENT}]📊 System Monitoring[/]")
        
        dashboard = await monitoring_system.get_dashboard_data()
        
        # Health status
        health = dashboard["health"]
        health_color = Colors.SUCCESS if health["overall_status"] == "healthy" else Colors.WARNING
        self.console.print(f"System Health: [{health_color}]{health['overall_status'].upper()}[/{health_color}]")
        
        # Performance metrics
        self.console.print(f"\n[{Colors.PRIMARY}]⚡ Performance Metrics[/]")
        for op, stats in dashboard["performance"].items():
            self.console.print(f"  {op}: [bold cyan]{stats.get('avg_ms', 0):.2f}ms[/] avg")

    async def run(self):
        """Main CLI loop"""
        self.print_banner()
        self.print_help()
        
        while True:
            try:
                cmd = Prompt.ask(
                    f"\n[{Colors.PRIMARY}]REDOPS[/][{Colors.ACCENT}]@[/][{Colors.SUCCESS}]AI[/][{Colors.TEXT_PRIMARY}] >[/]",
                    default="",
                    show_default=False
                )
                
                if not cmd.strip():
                    continue
                
                self.history.append(cmd)
                await self.handle_command(cmd)
                
            except (KeyboardInterrupt, EOFError):
                self.console.print(f"\n[{Colors.WARNING}]⚠️ Interrupted[/]")
                break
            except Exception as e:
                self.console.print(f"[{Colors.DANGER}]❌ Error: {str(e)}[/]")


async def main():
    cli = ModernCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())