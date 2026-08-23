"""
====================================================================
PROJECT REDOPS-AI - ROOT LAUNCHER
====================================================================
"""

import sys
import os
import argparse

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="REDOPS-AI - Autonomous RedOps Matrix")
    parser.add_argument("--mode", choices=["cli", "tui", "web"], default="cli", help="Execution mode (cli, tui, web)")
    args = parser.parse_args()

    if args.mode == "tui":
        import asyncio
        from cli.tui_cockpit import run_live_tui
        asyncio.run(run_live_tui(30))
    elif args.mode == "web":
        import uvicorn
        print("🌐 Starting REDOPS-AI Web Server at http://127.0.0.1:8000 ...")
        uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=False)
    else:
        from cli.interactive_cli import main
        main()

