# Run from PowerShell: .\scripts\start-vor-backend.ps1
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:VOR_DEMO_ENABLED = "true"
if (-not $env:VOR_DEMO_PASSWORD) { $env:VOR_DEMO_PASSWORD = "Victoria" }

Set-Location (Join-Path $RepoRoot "backend")
Write-Host "Starting FastAPI on http://127.0.0.1:8000 (demo enabled; email controlled by backend environment)"
if (Test-Path ".env") {
    uv run --no-sync --env-file .env uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
} else {
    uv run --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}
