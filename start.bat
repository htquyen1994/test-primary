@echo off
:: ============================================================
:: start.bat — Crypto Trading System startup (Windows batch)
:: Fallback if PowerShell execution policy blocks start.ps1
::
:: Usage:
::   start.bat           — start all services
::   start.bat --no-redis — skip Redis (already running)
:: ============================================================

setlocal enabledelayedexpansion

set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%

set BACKEND=%ROOT%\workspace\backend-workspace
set MOCK=%ROOT%\workspace\mock-exchange-workspace
set FRONTEND=%ROOT%\workspace\frontend-workspace
set TRADING_CORE=%ROOT%\workspace\trading-core

set BACKEND_PY=%BACKEND%\.venv\Scripts\python.exe
set MOCK_PY=%MOCK%\.venv\Scripts\python.exe
set BACKEND_CELERY=%BACKEND%\.venv\Scripts\celery.exe

echo.
echo ============================================================
echo   Crypto Trading System - Startup
echo ============================================================
echo.

:: ---- 1. Redis ----
if "%1"=="--no-redis" (
    echo [--] Skipping Redis
) else (
    echo [^>] Starting Redis...
    cd /d "%BACKEND%"
    docker compose up -d redis
    echo [OK] Redis started
    :: Wait 3s for Redis to be ready
    timeout /t 3 /nobreak > nul
)

:: ---- 2. Mock Exchange :8001 ----
echo [^>] Starting Mock Exchange :8001...
set PYTHONPATH=%TRADING_CORE%;%PYTHONPATH%
start "Mock Exchange :8001" /d "%MOCK%" cmd /k "%MOCK_PY% -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
timeout /t 4 /nobreak > nul

:: ---- 3. Backend API :8000 ----
echo [^>] Starting Backend API :8000...
if exist "%BACKEND%\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%BACKEND%\.env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)
start "Backend API :8000" /d "%BACKEND%" cmd /k "set PYTHONPATH=%TRADING_CORE%;%PYTHONPATH% && %BACKEND_PY% -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 4 /nobreak > nul

:: ---- 4. Data Pipeline ----
echo [^>] Starting Data Pipeline...
start "Data Pipeline" /d "%BACKEND%" cmd /k "set PYTHONPATH=%TRADING_CORE%;%PYTHONPATH% && %BACKEND_PY% main.py"

:: ---- 5. Celery Worker ----
echo [^>] Starting Celery Worker...
start "Celery Worker" /d "%BACKEND%" cmd /k "set PYTHONPATH=%TRADING_CORE%;%PYTHONPATH% && %BACKEND_CELERY% -A celery_app worker --loglevel=info -Q scoring,default --concurrency=2"

:: ---- 6. Frontend :5173 ----
echo [^>] Starting Frontend :5173...
if not exist "%FRONTEND%\node_modules" (
    echo [^>] Installing npm packages...
    cd /d "%FRONTEND%"
    call npm install
)
start "Frontend :5173" /d "%FRONTEND%" cmd /k "npm run dev"

:: ---- Summary ----
echo.
echo ============================================================
echo   All services launched in separate windows:
echo.
echo   Redis          :6379
echo   Mock Exchange  http://localhost:8001/docs
echo   Backend API    http://localhost:8000/docs
echo   Frontend       http://localhost:5173
echo.
echo   Run stop.bat to shut everything down.
echo ============================================================
echo.

endlocal
