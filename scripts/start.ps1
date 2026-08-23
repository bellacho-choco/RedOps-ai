param(
    [string]$Mode = "cli" # Options: "cli", "tui", "web", "docker"
)

$env:PYTHONIOENCODING = "utf-8"
Write-Host "⚡ [REDOPS-AI] Launching Real Security Intelligence Engine..." -ForegroundColor Cyan

if ($Mode -eq "docker") {
    Write-Host "🐳 Starting RedOps-AI via Docker Compose..." -ForegroundColor Magenta
    docker compose up --build -d redops-web
    Write-Host "✅ RedOps-AI Web Cockpit running on http://127.0.0.1:8000" -ForegroundColor Green
    Start-Process "http://127.0.0.1:8000"
} elseif ($Mode -eq "tui") {
    Write-Host "🚀 Launching Full-Screen Split Terminal Matrix..." -ForegroundColor Green
    python run.py --mode tui
} elseif ($Mode -eq "web") {
    Write-Host "🌐 Launching Web Cockpit Server on http://127.0.0.1:8000 ..." -ForegroundColor Magenta
    Start-Process "http://127.0.0.1:8000"
    python run.py --mode web
} else {
    Write-Host "💻 Launching Real Interactive CLI / TUI Command Center..." -ForegroundColor Yellow
    python run.py --mode cli
}
