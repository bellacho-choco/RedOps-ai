"""
====================================================================
PROJECT REDOPS-AI - INTERACTIVE TUI & CLI COMMAND CENTER
Real-time Tactical Terminal for 6-Agent Swarm, Live Scanners & Custom LLM
====================================================================
"""

import sys
import os
import asyncio
import time

# Ensure UTF-8 output on all consoles
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
from rich import box

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

console = Console()


def print_banner():
    accel = "CYTHON [C-SPEED]" if is_cython_accelerated() else "CYTHON [PURE-PY ACCELERATED]"
    llm_stat = llm_provider.get_status()
    banner_text = f"""[bold red]
██████╗ ███████╗██████╗  ██████╗ ██████╗ ███████╗      █████╗ ██╗
██╔══██╗██╔════╝██╔══██╗██╔═══██╗██╔══██╗██╔════╝     ██╔══██╗██║
██████╔╝█████╗  ██║  ██║██║   ██║██████╔╝███████╗     ███████║██║
██╔══██╗██╔══╝  ██║  ██║██║   ██║██╔═══╝ ╚════██║     ██╔══██║██║
██║  ██║███████╗██████╔╝╚██████╔╝██║     ███████║     ██║  ██║██║
╚═╝  ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝     ╚══════╝     ╚═╝  ╚═╝╚═╝
[/bold red]
[bold cyan]⚡ REDOPS-AI | REAL TUI/CLI AUTONOMOUS CYBER INTELLIGENCE ENGINE[/bold cyan]
[dim yellow]Swarm: 6 Hero Agents | Engine: Live Sockets & Real SAST | Acceleration: {accel}[/dim yellow]
[dim green]LLM Provider: {llm_stat['provider'].upper()} ({llm_stat['model']}) | Mode: {llm_stat['active_mode']}[/dim green]
"""
    console.print(banner_text)


def show_help():
    table = Table(title="[bold yellow]AVAILABLE TACTICAL COMMANDS[/bold yellow]", box=box.ROUNDED)
    table.add_column("Command", style="bold cyan", width=28)
    table.add_column("Description", style="white")

    table.add_row("chat [message]", "Chat with the RedOps AI Commander (or enter interactive Chat Mode)")
    table.add_row("agent <NAME> <message>", "Directly talk / inject directive to a specific Hero Agent")
    table.add_row("mission <target>", "Deploy full 6-agent autonomous swarm to assess real IP/domain")
    table.add_row("scan <target> [ports]", "Execute live async TCP port scan & banner grab on real host")
    table.add_row("audit <url>", "Perform live web security header, SSL certificate, & CORS audit")
    table.add_row("entropy <file_or_text>", "Run real Shannon entropy & secret pattern detection")
    table.add_row("graph", "Display live ASCII target topology and risk paths")
    table.add_row("report", "Display the latest mission debrief and mitigation report")
    table.add_row("llm status", "Check active LLM provider, model, and API connection status")
    table.add_row("llm config <p> <key> [m]", "Configure live LLM (gemini, openai, claude, custom)")
    table.add_row("skills [search_term]", "Search and list from 316+ indexed security playbooks")
    table.add_row("skill-read <name>", "Read full markdown playbook of a security skill")
    table.add_row("status", "Show live status and latest logs of all 6 hero agents")
    table.add_row("tui [duration_sec]", "Launch the full-screen 6-terminal split cockpit dashboard")
    table.add_row("clear", "Clear terminal screen")
    table.add_row("exit", "Exit RedOps-AI terminal")
    console.print(table)



async def handle_command(cmd_str: str):
    parts = cmd_str.strip().split(" ")
    if not parts or not parts[0]:
        return

    action = parts[0].lower()

    if action == "help":
        show_help()

    elif action == "chat":
        user_msg = cmd_str[4:].strip()
        if user_msg:
            # Single-turn chat
            console.print(f"\n[bold cyan]👤 You:[/] {user_msg}")
            with console.status("[bold red]👑 OVERLORD-PRIME reasoning...[/bold red]"):
                ctx = {"target": "Active Workspace", "open_ports": graph_engine.get_full_graph_state().get("nodes", [])}
                reply = await llm_provider.generate_cyber_reasoning("OVERLORD-PRIME (Supreme Commander)", user_msg, ctx)
            console.print(f"\n[bold red]👑 OVERLORD-PRIME:[/bold red]")
            console.print(Markdown(reply))
        else:
            # Interactive Continuous Chat Mode
            console.print("\n[bold magenta]═════════════════════════════════════════════════════════════════════[/bold magenta]")
            console.print("[bold magenta]💬 ENTERED INTERACTIVE CHAT MODE WITH REDOPS-AI COMMANDER[/bold magenta]")
            console.print("[dim]Ask any security questions, request attack surface advice, or issue mission orders.[/dim]")
            console.print("[dim]Type 'exit' or 'back' to return to normal CLI commands.[/dim]")
            console.print("[bold magenta]═════════════════════════════════════════════════════════════════════[/bold magenta]\n")
            
            while True:
                try:
                    chat_input = console.input("[bold magenta]REDOPS-CHAT 👑 > [/bold magenta]").strip()
                    if not chat_input:
                        continue
                    if chat_input.lower() in ["exit", "back", "quit"]:
                        console.print("[dim]Exiting Chat Mode. Returned to main CLI matrix.[/dim]")
                        break
                    
                    with console.status("[bold cyan]Analyzing context and generating response...[/bold cyan]"):
                        ctx = {"target": "Active Workspace", "graph_nodes": len(graph_engine.nodes)}
                        reply = await llm_provider.generate_cyber_reasoning("OVERLORD-PRIME Commander", chat_input, ctx)
                    
                    console.print(f"\n[bold red]👑 OVERLORD-PRIME:[/bold red]")
                    console.print(Markdown(reply))
                    console.print()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Chat mode exited.[/dim]")
                    break

    elif action == "agent":
        if len(parts) < 3:
            console.print("[red]Usage: agent <AGENT_NAME> <message_or_directive>[/red]")
            console.print("[dim]Available agents: OVERLORD-PRIME, SPECTRE-RECON, NEXUS-CYPHER, VORTEX-EXPLOIT, CIPHER-MORPH, CHRONO-DEBRIEF[/dim]")
            return
        
        agent_name = parts[1].upper()
        agent = swarm_matrix.get_agent(agent_name)
        if not agent:
            # Try fuzzy match
            matched = [k for k in swarm_matrix.agents.keys() if agent_name in k]
            if matched:
                agent = swarm_matrix.get_agent(matched[0])
                agent_name = matched[0]

        if not agent:
            console.print(f"[red]Agent '{parts[1]}' not found in matrix.[/red]")
            return

        directive = " ".join(parts[2:])
        console.print(f"[bold cyan]📡 Sending directive to [{agent.color_hex}]{agent_name}[/{agent.color_hex}]:[/bold cyan] {directive}")
        with console.status(f"[bold green]{agent_name} processing...[/bold green]"):
            response = await agent.process_task(directive)
        
        console.print(f"\n[{agent.color_hex}]● {agent_name} Response:[/{agent.color_hex}]")
        console.print(Markdown(response) if "\n" in response else response)

    elif action == "mission":

        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        console.print(f"\n[bold red]🚀 LAUNCHING AUTONOMOUS SWARM ON TARGET:[/] [bold yellow]{target}[/]")
        with console.status("[bold cyan]Swarm executing real multi-phase assessment...[/bold cyan]", spinner="dots"):
            result = await swarm_matrix.overlord.execute_mission(target)
        
        console.print("\n[bold green]✅ MISSION ACCOMPLISHED![/bold green]")
        console.print(f"• Target IP: [cyan]{result['scan_data'].get('ip')}[/cyan]")
        console.print(f"• Open Ports Found: [yellow]{result['scan_data'].get('open_ports_count', 0)}[/yellow]")
        console.print(f"• Scan Duration: [white]{result['scan_data'].get('scan_duration_s', 0)}s[/white]")

        # Print Debrief Report
        console.print("\n" + "="*70)
        console.print("[bold yellow]📋 EXECUTIVE MITIGATION DEBRIEF REPORT[/bold yellow]")
        console.print("="*70)
        console.print(Markdown(result["report"]))

    elif action == "scan":
        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        console.print(f"[bold cyan]🔍 Scanning TCP ports on {target}...[/bold cyan]")
        
        with console.status("[bold green]Probing socket endpoints...[/bold green]"):
            res = await socket_scanner.scan_target(target)

        table = Table(title=f"[bold green]SCAN RESULTS FOR {res['target']} ({res['ip']})[/bold green]", box=box.ROUNDED)
        table.add_column("Port", style="bold cyan", width=8)
        table.add_column("Protocol", style="magenta", width=10)
        table.add_column("Service", style="yellow", width=16)
        table.add_column("Latency (ms)", style="green", width=14)
        table.add_column("Banner / Info", style="white")

        for p in res.get("open_ports", []):
            table.add_row(str(p["port"]), p["protocol"], p["service"], f"{p['latency_ms']} ms", p["banner"])

        console.print(table)
        console.print(f"[dim]Total scanned: {res['total_probed']} ports in {res['scan_duration_s']}s. Open: {res['open_ports_count']}[/dim]")

        # Ingest into graph
        graph_engine.ingest_live_scan(res)

    elif action == "audit":
        url = parts[1] if len(parts) > 1 else "https://example.com"
        console.print(f"[bold cyan]🌐 Auditing Web Security Posture for {url}...[/bold cyan]")
        with console.status("[bold green]Inspecting HTTP headers & TLS ciphers...[/bold green]"):
            res = await web_auditor.audit_url(url)

        console.print(f"[bold]HTTP Status:[/] [green]{res.get('status_code')}[/green]")
        console.print(f"[bold]Server:[/] [cyan]{res['technology_stack'].get('server')}[/cyan] | [bold]X-Powered-By:[/] {res['technology_stack'].get('x_powered_by')}")
        
        # Missing Headers
        missing = res.get("missing_security_headers", [])
        if missing:
            console.print("\n[bold yellow]⚠️ Missing Security Headers:[/bold yellow]")
            for h in missing:
                console.print(f"  [-] [red]{h}[/red]")
        else:
            console.print("\n[bold green]✅ All primary security hardening headers are present![/bold green]")

        # Identified Risks
        risks = res.get("security_risks", [])
        if risks:
            r_table = Table(title="[bold red]DETECTED SECURITY RISKS[/bold red]", box=box.HEAVY)
            r_table.add_column("Risk ID", style="cyan", width=14)
            r_table.add_column("Severity", style="bold red", width=10)
            r_table.add_column("Title", style="white")
            for r in risks:
                r_table.add_row(r["id"], r["severity"], r["title"])
            console.print(r_table)

        # SSL details
        ssl_data = res.get("ssl_certificate", {})
        if ssl_data and "tls_version" in ssl_data:
            console.print(f"\n[bold green]🔒 SSL/TLS:[/] {ssl_data.get('tls_version')} ({ssl_data.get('cipher_suite')}) - Expires: {ssl_data.get('expires')}")

    elif action == "entropy":
        target = parts[1] if len(parts) > 1 else ""
        if not target:
            console.print("[red]Usage: entropy <filepath_or_text>[/red]")
            return

        if os.path.exists(target):
            console.print(f"[bold cyan]🧬 Analyzing local path:[/] {target}")
            if os.path.isdir(target):
                res = sast_auditor.analyze_directory(target)
                console.print(f"• Files scanned: {res['files_scanned']}")
                console.print(f"• Files with findings: {res['vulnerable_files_count']}")
                for f_res in res["findings_by_file"]:
                    console.print(f"\n📄 [yellow]{f_res['file']}[/yellow] ({f_res['total_findings']} findings):")
                    for f in f_res["findings"]:
                        console.print(f"   [{f['severity']}] {f['type']} -> {f['sample']} (Entropy: {f['entropy']:.2f})")
            else:
                f_res = sast_auditor.analyze_file(target)
                console.print(f"📄 [yellow]{f_res['file']}[/yellow] ({f_res['total_findings']} findings):")
                for f in f_res.get("findings", []):
                    console.print(f"   [{f['severity']}] {f['type']} -> {f['sample']} (Entropy: {f['entropy']:.2f})")
        else:
            # Analyze string directly
            findings = sast_auditor.analyze_buffer(target, source_name="Direct_Input")
            ent = calculate_shannon_entropy(target.encode('utf-8'))
            console.print(f"• Shannon Entropy: [bold yellow]{ent:.4f}[/bold yellow]")
            console.print(f"• Secret Patterns Found: [bold cyan]{len(findings)}[/bold cyan]")
            for f in findings:
                console.print(f"   [{f['severity']}] {f['type']} -> {f['sample']}")

    elif action == "graph":
        console.print(graph_engine.render_ascii_graph())

    elif action == "report":
        rep = swarm_matrix.overlord.last_assessment_report
        if rep:
            console.print(Markdown(rep))
        else:
            console.print("[dim]No mission report available. Run 'mission <target>' first.[/dim]")

    elif action == "llm":
        sub_action = parts[1].lower() if len(parts) > 1 else "status"
        if sub_action == "status":
            stat = llm_provider.get_status()
            p = Panel(
                f"[bold cyan]Provider:[/] {stat['provider'].upper()}\n"
                f"[bold cyan]Model:[/] {stat['model']}\n"
                f"[bold cyan]API Key Configured:[/] {'[green]YES[/green]' if stat['has_api_key'] else '[yellow]NO (Heuristic Mode Active)[/yellow]'}\n"
                f"[bold cyan]Active Mode:[/] {stat['active_mode']}\n"
                f"[bold cyan]Base Gateway:[/] {stat['base_url']}",
                title="[bold yellow]LLM REASONER STATUS[/bold yellow]",
                border_style="cyan"
            )
            console.print(p)
        elif sub_action == "config":
            if len(parts) < 4:
                console.print("[red]Usage: llm config <gemini|openai|claude|custom> <api_key> [model] [base_url][/red]")
                return
            provider_name = parts[2]
            key = parts[3]
            model = parts[4] if len(parts) > 4 else None
            base_url = parts[5] if len(parts) > 5 else None

            try:
                llm_provider.configure(provider_name, key, model, base_url)
                console.print(f"[bold green]✅ LLM Provider reconfigured to {provider_name.upper()}![/bold green]")
            except Exception as e:
                console.print(f"[bold red]Configuration error: {e}[/bold red]")

    elif action == "status":
        statuses = swarm_matrix.get_all_status()
        table = Table(title="[bold red]SWARM AGENT MATRIX STATUS[/bold red]", box=box.HEAVY)
        table.add_column("Hero Agent", style="bold cyan", width=18)
        table.add_column("Role", style="yellow", width=26)
        table.add_column("Status", style="bold green", width=12)
        table.add_column("Latest Log", style="white")

        for name, data in statuses.items():
            stat_style = "bold green" if data["status"] == "IDLE" else "bold red"
            table.add_row(name, data["role"], f"[{stat_style}]{data['status']}[/]", data["latest_log"][:65] + "...")
        console.print(table)

    elif action == "tui":
        duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
        await run_live_tui(duration)

    elif action == "skills":
        query = parts[1] if len(parts) > 1 else ""
        if query:
            results = skills_engine.search_skills(query, limit=20)
            table = Table(title=f"[bold yellow]SEARCH RESULTS FOR '{query}' ({len(results)} matches)[/bold yellow]", box=box.ROUNDED)
            table.add_column("Skill Name", style="bold cyan", width=25)
            table.add_column("Category", style="magenta", width=14)
            table.add_column("Description", style="white")
            for item in results:
                table.add_row(item["name"], item["category"], item["description"][:65] + "...")
            console.print(table)
        else:
            summary = skills_engine.get_summary()
            console.print(f"[bold cyan]⚡ Total Security Skills Indexed:[/bold cyan] [bold green]{summary['total_skills']}[/bold green]")
            for cat, count in summary["categories"].items():
                console.print(f"  • [bold yellow]{cat.upper():16}[/bold yellow] : {count} playbooks")

    elif action == "skill-read":
        if len(parts) < 2:
            console.print("[red]Usage: skill-read <skill_name>[/red]")
            return
        content = skills_engine.read_skill_content(parts[1])
        if content:
            console.print(Markdown(content[:2500]))
        else:
            console.print(f"[red]Skill '{parts[1]}' not found.[/red]")

    elif action == "clear":
        os.system("cls" if os.name == "nt" else "clear")
        print_banner()

    elif action == "exit" or action == "quit":
        console.print("[bold red]⚡ Terminating RedOps-AI Neural Matrix session...[/bold red]")
        sys.exit(0)

    else:
        console.print(f"[red]Unknown command: {parts[0]}. Type 'help' for tactical commands.[/red]")


async def main_cli_loop():
    print_banner()
    show_help()

    while True:
        try:
            cmd = console.input("\n[bold red]REDOPS[/bold red][bold cyan]@[/bold cyan][bold green]AI-MATRIX[/bold green][bold white] > [/bold white]")
            if not cmd.strip():
                continue
            await handle_command(cmd)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Session interrupted. Exiting...[/bold red]")
            break
        except Exception as e:
            console.print(f"[bold red]Execution error: {e}[/bold red]")


def main():
    try:
        asyncio.run(main_cli_loop())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

