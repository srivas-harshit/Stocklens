@echo off
REM ══════════════════════════════════════════════════════════════════
REM StockLens — Daily Dev Startup Script
REM Run this every time you want to start the app.
REM ══════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion
set ROOT=%~dp0
cd /d "%ROOT%"

echo.
echo ╔══════════════════════════════════════════╗
echo ║   StockLens — Starting Dev Servers       ║
echo ╚══════════════════════════════════════════╝
echo.

REM ── Check .env ───────────────────────────────────────────
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Run setup-first-time.bat first.
    pause
    exit /b 1
)

REM ── Check Docker ─────────────────────────────────────────
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running. Start it first.
    pause
    exit /b 1
)

REM ── Start/resume Docker infrastructure ───────────────────
echo [1/3] Starting Docker services (PostgreSQL + Redis)...
docker compose up -d postgres redis pgadmin
echo Waiting 5s for services to be ready...
timeout /t 5 /nobreak >nul

REM ── Start FastAPI backend ─────────────────────────────────
echo [2/3] Starting FastAPI backend on :8000 ...
start "StockLens API" cmd /k "cd /d %ROOT%apps\api && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM ── Optional: Start Upstox WebSocket worker ───────────────
REM Uncomment the line below once you have a valid Upstox access token in .env
REM start "StockLens Worker" cmd /k "cd /d %ROOT%apps\worker && python upstox_ws.py"

REM ── Start Next.js frontend ────────────────────────────────
echo [3/3] Starting Next.js frontend on :3000 ...
start "StockLens Web" cmd /k "cd /d %ROOT%apps\web && npm run dev"

echo.
echo ══════════════════════════════════════════════════════════════
echo  StockLens is starting up! (takes ~15 seconds on first run)
echo.
echo   Dashboard:   http://localhost:3000
echo   API:         http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   pgAdmin:     http://localhost:5050
echo   (pgAdmin login: admin@local.com / admin)
echo.
echo  Two new terminal windows opened for API and Web servers.
echo  Close them to stop the servers.
echo ══════════════════════════════════════════════════════════════
echo.
pause
