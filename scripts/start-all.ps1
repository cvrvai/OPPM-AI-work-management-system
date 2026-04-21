param(
    [switch]$Tunnel,
    [switch]$Docker
)

$Root = $PSScriptRoot

function Start-Service {
    param([string]$Name, [string]$ScriptPath)
    $ps = Start-Process powershell -ArgumentList "-NoExit", "-File", $ScriptPath `
        -WorkingDirectory (Split-Path $ScriptPath) `
        -PassThru
    Write-Host "  [$Name] started (PID $($ps.Id))"
    return $ps
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

    $tunnelLog = "$Root\tunnel.log"
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
            foreach ($l in (Get-Content $tunnelLog -ErrorAction SilentlyContinue)) {
                if ($l -match 'https://[a-zA-Z0-9\-]+\.trycloudflare\.com') {
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

    $envFile = "$Root\frontend\.env.local"
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
    # ── Docker mode: start all services via docker compose ──
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
    Write-Host "  Frontend  -> http://localhost:5173"
    if ($Tunnel -and $publicUrl) {
        Write-Host "  Webhook   -> $publicUrl/api/v1/git/webhook" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "To stop: docker compose -f docker-compose.microservices.yml -f docker-compose.dev.yml down" -ForegroundColor DarkGray

} else {
    # ── Native mode: start each service in its own window ──
    Write-Host ""
    Write-Host "Starting OPPM services..." -ForegroundColor Cyan

    $procs = @()
    $procs += Start-Service "core  (8000)" "$Root\services\core\start.ps1"
    $procs += Start-Service "ai    (8001)" "$Root\services\ai\start.ps1"
    $procs += Start-Service "git   (8002)" "$Root\services\git\start.ps1"

    Write-Host ""
    Write-Host "Starting frontend (5173)..." -ForegroundColor Cyan
    $frontendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "Set-Location '$Root\frontend'; npm run dev" `
        -WorkingDirectory "$Root\frontend" `
        -PassThru
    Write-Host "  [frontend] started (PID $($frontendProc.Id))"

    if ($Tunnel) {
        Write-Host ""
        Write-Host "Starting Cloudflare Tunnel on port 8002 (git service)..." -ForegroundColor Cyan
        $publicUrl = Start-CloudflaredTunnel -Port 8002
        if ($publicUrl) {
            Write-WebhookUrl -PublicUrl $publicUrl
            Write-Host "  NOTE: restart the Vite dev server to pick up the new URL." -ForegroundColor Yellow
        } else {
            Write-Host "  Could not detect tunnel URL within 30s. Check tunnel.log" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "All services running (native):" -ForegroundColor Green
    Write-Host "  Core API  -> http://localhost:8000"
    Write-Host "  AI        -> http://localhost:8001"
    Write-Host "  Git       -> http://localhost:8002"
    Write-Host "  Frontend  -> http://localhost:5173"
    if ($Tunnel -and $publicUrl) {
        Write-Host "  Webhook   -> $publicUrl/api/v1/git/webhook" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "To stop: close the terminal windows or Get-Process python,node | Stop-Process -Force" -ForegroundColor DarkGray
}

