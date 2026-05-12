<#
.SYNOPSIS
    Stop all Crypto Trading System services.

.DESCRIPTION
    Kills Python processes (uvicorn, main.py, celery),
    Node (vite dev server), and optionally stops Redis container.

.PARAMETER KeepRedis
    Keep Redis container running (default: stop it)

.EXAMPLE
    .\stop.ps1
    .\stop.ps1 -KeepRedis
#>

param([switch]$KeepRedis)

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

function Write-Step { param([string]$T) Write-Host "[>] $T" -ForegroundColor Yellow }
function Write-OK   { param([string]$T) Write-Host "[OK] $T" -ForegroundColor Green }

function Stop-ProcessOnPort {
    param([int]$Port, [string]$Name)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pid = $conn[0].OwningProcess
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-OK "Stopped $Name (PID $pid, :$Port)"
    } else {
        Write-Host "  [--] $Name not running on :$Port" -ForegroundColor Gray
    }
}

function Stop-ByPattern {
    param([string]$Pattern, [string]$Name)
    $procs = Get-Process | Where-Object { $_.CommandLine -like "*$Pattern*" } -ErrorAction SilentlyContinue
    if (-not $procs) {
        # Fallback: match by window title or main module
        $procs = Get-Process -Name "python", "uvicorn", "celery", "node" -ErrorAction SilentlyContinue |
                 Where-Object { $_.MainWindowTitle -like "*$Name*" }
    }
    if ($procs) {
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-OK "Stopped $Name"
    }
}

Write-Host ""
Write-Host ("=" * 50) -ForegroundColor Red
Write-Host "  Stopping all services..." -ForegroundColor Red
Write-Host ("=" * 50) -ForegroundColor Red

# Kill by port (most reliable)
Stop-ProcessOnPort 8000 "Backend API"
Stop-ProcessOnPort 8001 "Mock Exchange"
Stop-ProcessOnPort 5173 "Frontend"

# Kill any remaining Python and Node processes for this project
$Root = $PSScriptRoot
Write-Step "Killing remaining Python processes (uvicorn / celery / main.py)..."
Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*trade-workspace*" -or $_.CommandLine -like "*trade-workspace*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Get-Process -Name "celery" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Step "Killing Vite / Node dev server..."
Get-Process -Name "node" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*vite*" -or $_.CommandLine -like "*frontend-workspace*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

# Redis
if (-not $KeepRedis) {
    Write-Step "Stopping Redis container..."
    $BackendDir = Join-Path $Root "workspace\backend-workspace"
    if (Test-Path (Join-Path $BackendDir "docker-compose.yml")) {
        Push-Location $BackendDir
        docker compose stop redis 2>&1 | Out-Null
        Pop-Location
        Write-OK "Redis container stopped"
    }
} else {
    Write-Host "  [--] Redis kept running (-KeepRedis)" -ForegroundColor Gray
}

Write-Host ""
Write-OK "All services stopped."
Write-Host ""
