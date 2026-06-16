function Import-ProjectDotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootDir
    )

    $envFiles = @(
        (Join-Path $RootDir ".env"),
        (Join-Path $RootDir ".env.local"),
        (Join-Path $RootDir "backend\.env"),
        (Join-Path $RootDir "backend\.env.local"),
        (Join-Path $RootDir "frontend\.env.local"),
        (Join-Path $RootDir "frontend\.env.development.local")
    )

    foreach ($envFile in $envFiles) {
        if (-not (Test-Path $envFile)) {
            continue
        }

        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()

            if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
                return
            }

            if ($line.StartsWith("export ")) {
                $line = $line.Substring(7).Trim()
            }

            $equalsIndex = $line.IndexOf("=")
            if ($equalsIndex -le 0) {
                return
            }

            $name = $line.Substring(0, $equalsIndex).Trim()
            $value = $line.Substring($equalsIndex + 1).Trim()

            if ($value.Length -ge 2) {
                if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
            }

            if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, "Process"))) {
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
}

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Assert-TokenFormat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -notmatch '^\d+:[A-Za-z0-9_-]+$') {
        throw "$Name does not look like a Telegram bot token. Expected format: 1234567890:ABC..."
    }
}

function Get-TelegramBotInfo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BotToken
    )

    try {
        return Invoke-RestMethod -Uri "https://api.telegram.org/bot$BotToken/getMe"
    }
    catch {
        throw "Telegram getMe failed for TELEGRAM_DEV_BOT_TOKEN. Check that the dev bot token is valid."
    }
}

function Assert-TelegramDevEnvironment {
    $botToken = $env:TELEGRAM_BOT_TOKEN
    $devBotToken = $env:TELEGRAM_DEV_BOT_TOKEN
    $devBotUsername = $env:TELEGRAM_DEV_BOT_USERNAME
    $secretToken = $env:TELEGRAM_WEBHOOK_SECRET

    $missing = @()

    if ([string]::IsNullOrWhiteSpace($botToken)) {
        $missing += "TELEGRAM_BOT_TOKEN"
    }

    if ([string]::IsNullOrWhiteSpace($devBotToken)) {
        $missing += "TELEGRAM_DEV_BOT_TOKEN"
    }

    if ([string]::IsNullOrWhiteSpace($devBotUsername)) {
        $missing += "TELEGRAM_DEV_BOT_USERNAME"
    }

    if ([string]::IsNullOrWhiteSpace($secretToken)) {
        $missing += "TELEGRAM_WEBHOOK_SECRET"
    }

    if ($missing.Count -gt 0) {
        $names = $missing -join ", "
        throw @"
Missing Telegram local dev environment values: $names

Local Telegram testing must use a separate dev bot.
Add these values to backend/.env:

TELEGRAM_BOT_TOKEN=<dev-bot-token>
TELEGRAM_DEV_BOT_TOKEN=<dev-bot-token>
TELEGRAM_DEV_BOT_USERNAME=<dev-bot-username>
TELEGRAM_WEBHOOK_SECRET=<local-secret>

Then run:
task dev:telegram
"@
    }

    Assert-TokenFormat -Name "TELEGRAM_DEV_BOT_TOKEN" -Value $devBotToken
    Assert-TokenFormat -Name "TELEGRAM_BOT_TOKEN" -Value $botToken

    if ($botToken -ne $devBotToken) {
        throw @"
Refusing to run task dev:telegram.

For safe local Telegram testing, local TELEGRAM_BOT_TOKEN must equal TELEGRAM_DEV_BOT_TOKEN.
This prevents local polling from using the production Telegram bot.

Fix backend/.env so both values use the dev bot token.
"@
    }

    $botInfo = Get-TelegramBotInfo -BotToken $devBotToken
    if (-not $botInfo.ok) {
        throw "Telegram getMe returned ok=false for TELEGRAM_DEV_BOT_TOKEN."
    }

    $actualUsername = [string]$botInfo.result.username
    if ($actualUsername -ne $devBotUsername) {
        throw @"
Refusing to run task dev:telegram.

TELEGRAM_DEV_BOT_TOKEN belongs to @$actualUsername, but backend/.env expects @$devBotUsername.
Update TELEGRAM_DEV_BOT_USERNAME or use the correct dev bot token.
"@
    }
}

$ErrorActionPreference = "Stop"

$rootDir = Get-ProjectRoot
Import-ProjectDotEnv -RootDir $rootDir
Assert-TelegramDevEnvironment

Write-Host "Telegram local dev preflight passed."
Write-Host "Local backend and polling will use the configured dev Telegram bot only."
Write-Host "Production Telegram webhook will not be touched by task dev:telegram."
