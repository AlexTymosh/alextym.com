param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health/live" -TimeoutSec 5 | Out-Null
} catch {
    Write-Error "Backend is not reachable at http://127.0.0.1:$BackendPort/api/health/live. Start local servers with: task dev"
    exit 1
}

try {
    Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 5 | Out-Null
} catch {
    Write-Error "Frontend is not reachable at http://127.0.0.1:$FrontendPort. Start local servers with: task dev"
    exit 1
}

Write-Host "Local smoke check passed."
