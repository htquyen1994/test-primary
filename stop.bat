@echo off
:: ============================================================
:: stop.bat — Stop all Crypto Trading System services
::
:: Usage:
::   stop.bat           — stop all including Redis
::   stop.bat --keep-redis
:: ============================================================

echo.
echo ============================================================
echo   Stopping Crypto Trading System services...
echo ============================================================
echo.

:: Kill by port
echo [^>] Stopping Backend API :8000...
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%P /F > nul 2>&1
    echo [OK] Killed PID %%P
)

echo [^>] Stopping Mock Exchange :8001...
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    taskkill /PID %%P /F > nul 2>&1
    echo [OK] Killed PID %%P
)

echo [^>] Stopping Frontend :5173...
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%P /F > nul 2>&1
    echo [OK] Killed PID %%P
)

:: Kill celery
echo [^>] Stopping Celery workers...
taskkill /IM celery.exe /F > nul 2>&1

:: Redis
if "%1"=="--keep-redis" (
    echo [--] Redis kept running
) else (
    echo [^>] Stopping Redis container...
    cd /d "%~dp0workspace\backend-workspace"
    docker compose stop redis > nul 2>&1
    echo [OK] Redis stopped
)

echo.
echo [OK] All services stopped.
echo.
