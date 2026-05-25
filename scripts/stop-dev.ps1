param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "SilentlyContinue"

$currentPid = $PID
$stoppedProcessIds = @{}
$patterns = @("uvicorn app\.main:app", "next dev")

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.ProcessId -ne $currentPid -and
        $_.CommandLine -and
        ($_.CommandLine -match $patterns[0] -or $_.CommandLine -match $patterns[1])
    }

foreach ($process in $processes) {
    Write-Host ("Stopping PID {0}: {1}" -f $process.ProcessId, $process.CommandLine)
    Stop-Process -Id $process.ProcessId -Force
    $stoppedProcessIds[$process.ProcessId] = $true
}

$ports = @($BackendPort, $FrontendPort)

foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue

    foreach ($connection in $connections) {
        $ownerPid = $connection.OwningProcess

        if (-not $ownerPid -or $ownerPid -eq $currentPid -or $stoppedProcessIds.ContainsKey($ownerPid)) {
            continue
        }

        $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue

        if ($owner) {
            Write-Host ("Stopping {0} PID {1} on port {2}" -f $owner.ProcessName, $ownerPid, $port)
            Stop-Process -Id $ownerPid -Force
            $stoppedProcessIds[$ownerPid] = $true
        }
    }
}

if ($stoppedProcessIds.Count -eq 0) {
    Write-Host "No local dev server processes found."
}
