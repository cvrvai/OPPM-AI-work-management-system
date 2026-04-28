param(
    [switch]$Tunnel,
    [switch]$Docker
)

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Start-ServiceWindow {
    param(
        [string]$Name,
        [string]$ScriptPath
    )

    if (-not (Test-Path $ScriptPath)) {
        Write-Host "  [$Name] script not found: $ScriptPath" -ForegroundColor Red
        return $null
    }

    $logDir = Join-Path $Root "logs\dev-startup"
    if (-not (Test-Path $logDir)) {
        New-Item -Path $logDir -ItemType Directory | Out-Null
    }

    $safeName = (($Name -replace '[^a-zA-Z0-9]+', '-') -replace '^-|-$', '').ToLowerInvariant()
    $logFile = Join-Path $logDir ("{0}.log" -f $safeName)
    $serviceDir = Split-Path $ScriptPath

    $command = @"
Set-Location '$serviceDir'
& '$ScriptPath' *>&1 | Tee-Object -FilePath '$logFile' -Append
if (`$LASTEXITCODE -and `$LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[$Name] exited with code '`$LASTEXITCODE'.' -ForegroundColor Red
    Write-Host 'Log file: $logFile' -ForegroundColor Yellow
    Write-Host 'Press Enter to close this window.' -ForegroundColor DarkGray
    Read-Host | Out-Null
}
"@

    $ps = Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command `
        -WorkingDirectory (Split-Path $ScriptPath) `
        -PassThru
    Write-Host "  [$Name] started (PID $($ps.Id)) log: $logFile"
    return $ps
}

function Start-FrontendWindow {
    $frontendPath = Join-Path $Root "frontend"
    $command = "Set-Location '$frontendPath'; npm run dev:native"
    $ps = Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command `
        -WorkingDirectory $frontendPath `
        -PassThru
    Write-Host "  [frontend] started (PID $($ps.Id))"
    return $ps
}

function Wait-ForHttpEndpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod $Url -TimeoutSec 3
            Write-Host "  [$Name] ready at $Url" -ForegroundColor Green
            return $true
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    Write-Host "  [$Name] is still starting. If the frontend shows proxy errors, check $Url in a new terminal." -ForegroundColor Yellow
    return $false
}

function Start-CloudflaredTunnel {
    param([string]$Port)
    $cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (-not (Test-Path $cloudflared)) {
        $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
        $cloudflared = if ($cmd) { $cmd.Source } else { $null }
    }
    if (-not $cloudflared) {
        Write-Host "  cloudflared not found. Install via: winget install Cloudflare.cloudflared" -ForegroundColor Red
        return $null
    }

    $tunnelLog = Join-Path $Root "tunnel.log"
    if (Test-Path $tunnelLog) { Remove-Item $tunnelLog }

    $cfExe = $cloudflared
    $cfLog = $tunnelLog
    $tunnelJob = Start-Job -ScriptBlock {
        & $using:cfExe tunnel --url "http://localhost:$using:Port" 2>&1 | Out-File -FilePath $using:cfLog -Encoding utf8
    }
    Write-Host "  [tunnel] job started (JobId $($tunnelJob.Id)) -- waiting for URL..."

    $publicUrl = $null
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline -and -not $publicUrl) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $tunnelLog) {
            foreach ($line in (Get-Content $tunnelLog -ErrorAction SilentlyContinue)) {
                if ($line -match 'https://[a-zA-Z0-9\-]+\.trycloudflare\.com') {
                    $publicUrl = $Matches[0]
                    break
                }
            }
        }
    }
    return $publicUrl
}

function Write-WebhookUrl {
    param([string]$PublicUrl)
    $webhookUrl = "$PublicUrl/api/v1/git/webhook"
    Write-Host ""
    Write-Host "  Tunnel URL:  $PublicUrl" -ForegroundColor Green
    Write-Host "  Webhook URL: $webhookUrl" -ForegroundColor Green
    Write-Host ""
    Write-Host "  >> Paste this into GitHub Settings > Webhooks > Payload URL:" -ForegroundColor Yellow
    Write-Host "     $webhookUrl" -ForegroundColor White

    $envFile = Join-Path $Root "frontend\.env.local"
    $envLine = "VITE_WEBHOOK_BASE_URL=$PublicUrl"
    if (Test-Path $envFile) {
        $existing = Get-Content $envFile | Where-Object { $_ -notmatch '^VITE_WEBHOOK_BASE_URL=' }
        $existing + $envLine | Set-Content $envFile
    } else {
        $envLine | Set-Content $envFile
    }
    Write-Host "  Written to frontend/.env.local" -ForegroundColor DarkGray
}

$publicUrl = $null

if ($Docker) {
    Write-Host ""
    Write-Host "Starting OPPM stack with Docker Compose..." -ForegroundColor Cyan
    $composeArgs = "-f docker-compose.microservices.yml -f docker-compose.dev.yml up -d --build"
    $cp = Start-Process "docker" -ArgumentList "compose $composeArgs" `
        -WorkingDirectory $Root -Wait -PassThru -NoNewWindow
    if ($cp.ExitCode -ne 0) {
        Write-Host "  docker compose failed (exit $($cp.ExitCode)). Check output above." -ForegroundColor Red
        exit 1
    }
    Write-Host "  All containers started." -ForegroundColor Green

    if ($Tunnel) {
        Write-Host ""
        Write-Host "Starting Cloudflare Tunnel on port 80 (gateway)..." -ForegroundColor Cyan
        $publicUrl = Start-CloudflaredTunnel -Port 80
        if ($publicUrl) {
            Write-WebhookUrl -PublicUrl $publicUrl
            Write-Host "  NOTE: restart the frontend container to pick up the new VITE_WEBHOOK_BASE_URL:" -ForegroundColor Yellow
            Write-Host "    docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml restart frontend" -ForegroundColor DarkGray
        } else {
            Write-Host "  Could not detect tunnel URL within 30s. Check tunnel.log" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "All services running (Docker):" -ForegroundColor Green
    Write-Host "  Gateway   -> http://localhost:80"
    Write-Host "  Core API  -> http://localhost:8000"
    Write-Host "  AI        -> http://localhost:8001"
    Write-Host "  Git       -> http://localhost:8002"
    Write-Host "  MCP       -> http://localhost:8003"
    Write-Host "  Frontend  -> http://localhost:5173"
    if ($Tunnel -and $publicUrl) {
        Write-Host "  Webhook   -> $publicUrl/api/v1/git/webhook" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "To stop: docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml down" -ForegroundColor DarkGray
} else {
    Write-Host ""
    Write-Host "Starting OPPM services..." -ForegroundColor Cyan

    $procs = @()
    $procs += Start-ServiceWindow "gateway (8080)" (Join-Path $Root "services\gateway\start.ps1")
    $procs += Start-ServiceWindow "core    (8000)" (Join-Path $Root "services\core\start.ps1")
    $procs += Start-ServiceWindow "ai      (8001)" (Join-Path $Root "services\ai\start.ps1")
    $procs += Start-ServiceWindow "git     (8002)" (Join-Path $Root "services\git\start.ps1")
    $procs += Start-ServiceWindow "mcp     (8003)" (Join-Path $Root "services\mcp\start.ps1")

    Write-Host ""
    Write-Host "Waiting for gateway and core to become reachable..." -ForegroundColor Cyan
    $null = Wait-ForHttpEndpoint "gateway" "http://127.0.0.1:8080/health"
    $null = Wait-ForHttpEndpoint "core" "http://127.0.0.1:8000/health"

    Write-Host ""
    Write-Host "Starting frontend (5173) with native gateway proxy..." -ForegroundColor Cyan
    $frontendProc = Start-FrontendWindow

    if ($Tunnel) {
        Write-Host ""
        Write-Host "Starting Cloudflare Tunnel on port 8080 (gateway)..." -ForegroundColor Cyan
        $publicUrl = Start-CloudflaredTunnel -Port 8080
        if ($publicUrl) {
            Write-WebhookUrl -PublicUrl $publicUrl
            Write-Host "  NOTE: restart the Vite dev server to pick up the new URL." -ForegroundColor Yellow
        } else {
            Write-Host "  Could not detect tunnel URL within 30s. Check tunnel.log" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "All services running (native):" -ForegroundColor Green
    Write-Host "  Gateway   -> http://localhost:8080"
    Write-Host "  Core API  -> http://localhost:8000"
    Write-Host "  AI        -> http://localhost:8001"
    Write-Host "  Git       -> http://localhost:8002"
    Write-Host "  MCP       -> http://localhost:8003"
    Write-Host "  Frontend  -> http://localhost:5173"
    if ($Tunnel -and $publicUrl) {
        Write-Host "  Webhook   -> $publicUrl/api/v1/git/webhook" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "If a service fails, its PowerShell window will stay open and the latest output is written to logs/dev-startup/." -ForegroundColor Cyan
    Write-Host "Launcher finished. Service logs continue in the separate PowerShell windows this script opened." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To stop: close the terminal windows or Get-Process python,node | Stop-Process -Force" -ForegroundColor DarkGray
}