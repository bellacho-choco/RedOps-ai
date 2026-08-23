"""
====================================================================
PROJECT REDOPS-OMEGA - UNIFIED CLI ENTRY POINT
`redops --mode cli|server` single installable entry (PLAN Step 11).
====================================================================
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="redops",
        description="REDOPS-OMEGA autonomous adversarial security platform")
    parser.add_argument("--mode", choices=["cli", "server"], default="cli",
                        help="cli = interactive TUI; server = FastAPI app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=12000)
    args = parser.parse_args()

    if args.mode == "server":
        import uvicorn
        uvicorn.run("backend.server:app", host=args.host, port=args.port)
        return 0

    from cli.interactive_cli import main as cli_main
    cli_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
