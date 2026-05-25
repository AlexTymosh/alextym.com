param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health/live" -TimeoutSec 5 | Out-Null
Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 5 | Out-Null

Write-Host "Local smoke check passed."
