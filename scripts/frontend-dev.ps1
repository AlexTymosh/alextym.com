param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

$env:BACKEND_ORIGIN = "http://127.0.0.1:$BackendPort"
npm run dev -- -H 127.0.0.1 -p $FrontendPort

