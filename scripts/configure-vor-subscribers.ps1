# Writes two contact addresses to the ignored backend/.env, without modifying other keys.
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[^\s@]+@[^\s@]+\.[^\s@]+$')][string]$AlexEmail,
    [Parameter(Mandatory=$true)][ValidatePattern('^[^\s@]+@[^\s@]+\.[^\s@]+$')][string]$VictoriaEmail
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$path = Join-Path $repo 'backend\.env'
$keep = New-Object 'System.Collections.Generic.List[string]'
if (Test-Path $path) {
    foreach ($line in [System.IO.File]::ReadAllLines($path)) {
        if ($line -notmatch '^\s*VOR_DEMO_(ALEX|VICTORIA)_EMAIL\s*=') { [void]$keep.Add($line) }
    }
}
[void]$keep.Add('VOR_DEMO_ALEX_EMAIL=' + $AlexEmail.Trim().ToLowerInvariant())
[void]$keep.Add('VOR_DEMO_VICTORIA_EMAIL=' + $VictoriaEmail.Trim().ToLowerInvariant())
[System.IO.File]::WriteAllLines($path, $keep.ToArray(), (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Two Fleet VOR contact emails saved to ignored backend/.env. Restart backend to apply.'
