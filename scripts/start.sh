#!/bin/bash
# REDOPS-AI Linux/MacOS Launcher Script

MODE="${1:-cli}"
export PYTHONIOENCODING="utf-8"

echo -e "\033[1;36m⚡ [REDOPS-AI] Launching Real Security Intelligence Engine...\033[0m"

if [ "$MODE" == "docker" ]; then
    echo -e "\033[1;35m🐳 Starting RedOps-AI via Docker Compose...\033[0m"
    docker compose up --build -d redops-web
    echo -e "\033[1;32m✅ RedOps-AI Web Cockpit running on http://127.0.0.1:8000\033[0m"
elif [ "$MODE" == "tui" ]; then
    echo -e "\033[1;32m🚀 Launching Full-Screen Split Terminal Matrix...\033[0m"
    python3 run.py --mode tui
elif [ "$MODE" == "web" ]; then
    echo -e "\033[1;35m🌐 Launching Web Cockpit Server on http://127.0.0.1:8000 ...\033[0m"
    python3 run.py --mode web
else
    echo -e "\033[1;33m💻 Launching Real Interactive CLI / TUI Command Center...\033[0m"
    python3 run.py --mode cli
fi
