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
    parser.add_argument("--mode", choices=["cli", "modern-cli", "tui", "web"], default="cli", help="Execution mode (cli, modern-cli, tui, web)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address for web server (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    if args.mode == "tui":
        import asyncio
        from cli.tui_cockpit import run_live_tui
        asyncio.run(run_live_tui(30))
    elif args.mode == "web":
        import uvicorn
        print(f"🌐 Starting REDOPS-AI Web Server at http://{args.host}:{args.port} (reload={args.reload}) ...")
        uvicorn.run("backend.server:app", host=args.host, port=args.port, reload=args.reload)
    elif args.mode == "modern-cli":
        import asyncio
        from cli.modern_cli import main
        asyncio.run(main())
    else:
        from cli.interactive_cli import main
        main()

