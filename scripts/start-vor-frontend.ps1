# Run in another PowerShell: .\scripts\start-vor-frontend.ps1
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:BACKEND_ORIGIN = "http://127.0.0.1:8000"
Set-Location (Join-Path $RepoRoot "frontend")
Write-Host "Starting Next.js at http://localhost:3000/fleet-vor-hub"
npm run dev
