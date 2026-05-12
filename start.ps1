<#
.SYNOPSIS
    Start all Crypto Trading System services.

.DESCRIPTION
    Starts services in dependency order:
      1. Redis            (Docker)
      2. Mock Exchange    (FastAPI :8001)
      3. Backend API      (FastAPI :8000)
      4. Data Pipeline    (asyncio)
      5. Celery Worker    (trade execution)
      6. Frontend         (Vite :5173)

.PARAMETER Mode
    dev  (default) — all services with hot-reload
    prod           — no hot-reload, optimized

.PARAMETER SkipRedis
    Skip Redis startup (if already running)

.PARAMETER Services
    Comma-separated subset to start, e.g. "backend,frontend"
    Options: redis, mock-exchange, backend-api, data-pipeline, celery, frontend

.EXAMPLE
    .\start.ps1
    .\start.ps1 -SkipRedis
    .\start.ps1 -Services "backend-api,frontend"
    .\start.ps1 -Mode prod
#>

param(
    [ValidateSet("dev", "prod")]
    [string]$Mode = "dev",

    [switch]$SkipRedis,

    [string]$Services = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$Root          = $PSScriptRoot
$BackendDir    = Join-Path $Root "workspace\backend-workspace"
$MockDir       = Join-Path $Root "workspace\mock-exchange-workspace"
$FrontendDir   = Join-Path $Root "workspace\frontend-workspace"
$TradingCore   = Join-Path $Root "workspace\trading-core"

$BackendVenv   = Join-Path $BackendDir ".venv\Scripts\python.exe"
$MockVenv      = Join-Path $MockDir    ".venv\Scripts\python.exe"
$BackendPip    = Join-Path $BackendDir ".venv\Scripts\pip.exe"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Step {
    param([string]$Text, [string]$Color = "Yellow")
    Write-Host "[>] $Text" -ForegroundColor $Color
}

function Write-OK   { param([string]$T) Write-Host "[OK] $T"    -ForegroundColor Green }
function Write-Warn { param([string]$T) Write-Host "[!!] $T"    -ForegroundColor Yellow }
function Write-Err  { param([string]$T) Write-Host "[ERR] $T"   -ForegroundColor Red }

function Test-Port {
    param([int]$Port, [int]$TimeoutMs = 500)
    try {
        $tcp = [System.Net.Sockets.TcpClient]::new()
        $task = $tcp.ConnectAsync("127.0.0.1", $Port)
        if ($task.Wait($TimeoutMs)) { $tcp.Close(); return $true }
        $tcp.Close()
    } catch {}
    return $false
}

function Wait-Port {
    param([int]$Port, [string]$Name, [int]$TimeoutSec = 30)
    Write-Step "Waiting for $Name (:$Port)..."
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { Write-OK "$Name is up (:$Port)"; return $true }
        Start-Sleep -Milliseconds 500
    }
    Write-Warn "$Name did not respond on :$Port after ${TimeoutSec}s"
    return $false
}

function Should-Run {
    param([string]$ServiceName)
    if ($Services -eq "all") { return $true }
    return ($Services -split ",") -contains $ServiceName
}

function Open-ServiceWindow {
    param(
        [string]$Title,
        [string]$WorkDir,
        [string]$Command,
        [string]$Color = "DarkBlue"
    )
    $escaped = $Command -replace '"', '\"'
    $args = "-NoExit -Command `"Set-Location '$WorkDir'; Write-Host '--- $Title ---' -ForegroundColor Cyan; $escaped`""
    Start-Process powershell -ArgumentList $args -WindowStyle Normal
    Write-OK "Started: $Title"
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
Write-Header "Crypto Trading System — Startup"
Write-Host "  Mode:     $Mode" -ForegroundColor White
Write-Host "  Services: $Services" -ForegroundColor White
Write-Host "  Root:     $Root" -ForegroundColor Gray

# Check Docker
if ((Should-Run "redis") -and -not $SkipRedis) {
    try {
        $null = docker version 2>&1
    } catch {
        Write-Err "Docker not found. Install Docker Desktop or use -SkipRedis if Redis is already running."
        exit 1
    }
}

# Check Node
if (Should-Run "frontend") {
    try { $null = node --version 2>&1 } catch {
        Write-Err "Node.js not found. Install from https://nodejs.org"
        exit 1
    }
}

# Check Python venvs
foreach ($venv in @($BackendVenv, $MockVenv)) {
    if (-not (Test-Path $venv)) {
        $dir = Split-Path (Split-Path $venv -Parent) -Parent
        Write-Warn "venv not found at $venv"
        Write-Step "Creating venv in $dir ..."
        python -m venv (Join-Path $dir ".venv")
        & (Join-Path $dir ".venv\Scripts\pip.exe") install -r (Join-Path $dir "requirements.txt") -q
        Write-OK "venv created"
    }
}

# ---------------------------------------------------------------------------
# 1. Redis
# ---------------------------------------------------------------------------
if ((Should-Run "redis") -and -not $SkipRedis) {
    Write-Header "1/6  Redis"
    if (Test-Port 6379) {
        Write-OK "Redis already running on :6379"
    } else {
        Write-Step "Starting Redis via Docker Compose..."
        Push-Location $BackendDir
        docker compose up -d redis
        Pop-Location
        Wait-Port 6379 "Redis" 20 | Out-Null
    }
} else {
    Write-Warn "Skipping Redis startup"
}

# ---------------------------------------------------------------------------
# 2. Mock Exchange  (:8001)
# ---------------------------------------------------------------------------
if (Should-Run "mock-exchange") {
    Write-Header "2/6  Mock Exchange (:8001)"
    if (Test-Port 8001) {
        Write-OK "Mock Exchange already running on :8001"
    } else {
        $env_block = @"
`$env:PYTHONPATH = '$TradingCore;' + `$env:PYTHONPATH
"@
        $cmd = if ($Mode -eq "dev") {
            "$env_block; & '$MockVenv' -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
        } else {
            "$env_block; & '$MockVenv' -m uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1"
        }
        Open-ServiceWindow "Mock Exchange :8001" $MockDir $cmd
        Wait-Port 8001 "Mock Exchange" 20 | Out-Null
    }
}

# ---------------------------------------------------------------------------
# 3. Backend API  (:8000)
# ---------------------------------------------------------------------------
if (Should-Run "backend-api") {
    Write-Header "3/6  Backend API (:8000)"
    if (Test-Port 8000) {
        Write-OK "Backend API already running on :8000"
    } else {
        # Load .env if present
        $envFile = Join-Path $BackendDir ".env"
        $envLoad = if (Test-Path $envFile) {
            "Get-Content '$envFile' | ForEach-Object { if (`$_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1].Trim(), `$matches[2].Trim(), 'Process') } }; "
        } else { "" }

        $cmd = if ($Mode -eq "dev") {
            "$envLoad`$env:PYTHONPATH = '$TradingCore;' + `$env:PYTHONPATH; & '$BackendVenv' -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
        } else {
            "$envLoad`$env:PYTHONPATH = '$TradingCore;' + `$env:PYTHONPATH; & '$BackendVenv' -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2"
        }
        Open-ServiceWindow "Backend API :8000" $BackendDir $cmd
        Wait-Port 8000 "Backend API" 30 | Out-Null
    }
}

# ---------------------------------------------------------------------------
# 4. Data Pipeline  (asyncio)
# ---------------------------------------------------------------------------
if (Should-Run "data-pipeline") {
    Write-Header "4/6  Data Pipeline (OHLCV / OB / Delta / Scoring)"
    $envFile = Join-Path $BackendDir ".env"
    $envLoad = if (Test-Path $envFile) {
        "Get-Content '$envFile' | ForEach-Object { if (`$_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1].Trim(), `$matches[2].Trim(), 'Process') } }; "
    } else { "" }

    $cmd = "$envLoad`$env:PYTHONPATH = '$TradingCore;' + `$env:PYTHONPATH; & '$BackendVenv' main.py"
    Open-ServiceWindow "Data Pipeline" $BackendDir $cmd
    Write-OK "Data Pipeline started"
}

# ---------------------------------------------------------------------------
# 5. Celery Worker  (trade execution tasks)
# ---------------------------------------------------------------------------
if (Should-Run "celery") {
    Write-Header "5/6  Celery Worker"
    $envFile = Join-Path $BackendDir ".env"
    $envLoad = if (Test-Path $envFile) {
        "Get-Content '$envFile' | ForEach-Object { if (`$_ -match '^([^#][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1].Trim(), `$matches[2].Trim(), 'Process') } }; "
    } else { "" }

    $celeryExe = Join-Path $BackendDir ".venv\Scripts\celery.exe"
    $cmd = "$envLoad`$env:PYTHONPATH = '$TradingCore;' + `$env:PYTHONPATH; & '$celeryExe' -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2"
    Open-ServiceWindow "Celery Worker" $BackendDir $cmd
    Write-OK "Celery Worker started"
}

# ---------------------------------------------------------------------------
# 6. Frontend  (:5173)
# ---------------------------------------------------------------------------
if (Should-Run "frontend") {
    Write-Header "6/6  Frontend (:5173)"
    if (Test-Port 5173) {
        Write-OK "Frontend already running on :5173"
    } else {
        # Install deps if node_modules missing
        if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
            Write-Step "Installing npm dependencies..."
            Push-Location $FrontendDir
            npm install --silent
            Pop-Location
            Write-OK "npm install done"
        }
        $cmd = "npm run dev"
        Open-ServiceWindow "Frontend :5173" $FrontendDir $cmd
        Wait-Port 5173 "Frontend" 20 | Out-Null
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Header "All Services Started"

$checks = @(
    @{ Name = "Redis";          Port = 6379 }
    @{ Name = "Mock Exchange";  Port = 8001 }
    @{ Name = "Backend API";    Port = 8000 }
    @{ Name = "Frontend";       Port = 5173 }
)

foreach ($svc in $checks) {
    $up = Test-Port $svc.Port
    $status = if ($up) { "[UP]  " } else { "[DOWN]" }
    $color  = if ($up) { "Green" } else { "Red" }
    Write-Host "  $status $($svc.Name.PadRight(16)) http://localhost:$($svc.Port)" -ForegroundColor $color
}

Write-Host ""
Write-Host "  Dashboard:  " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Cyan
Write-Host "  Backend:    " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Mock Exch:  " -NoNewline; Write-Host "http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Run .\stop.ps1 to shut everything down." -ForegroundColor Gray
Write-Host ""
