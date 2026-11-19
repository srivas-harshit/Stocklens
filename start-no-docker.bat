@echo off
REM ================================================================
REM StockLens - Start Without Docker (No Docker Desktop needed)
REM Run this every time you want to start the app.
REM ================================================================
setlocal enabledelayedexpansion
set ROOT=%~dp0
cd /d "%ROOT%"

echo.
echo  StockLens - Starting (No Docker Mode)
echo  =======================================
echo.

REM ── Check .env ───────────────────────────────────────────────
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Run setup-no-docker.ps1 as Administrator first.
    pause
    exit /b 1
)
echo [OK] .env found.

REM ── Check Python ─────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo   Download from: https://www.python.org/downloads/
    echo   IMPORTANT: During install, check "Add Python to PATH"
    echo   Then close and re-open this window.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v found.

REM ── Check Node.js ────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Node.js is not installed or not in PATH.
    echo.
    echo   Download from: https://nodejs.org (choose LTS version)
    echo   Then close and re-open this window.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [OK] Node.js %%v found.

REM ── Check / start PostgreSQL service ─────────────────────────
echo.
echo [DB] Checking PostgreSQL...
sc query postgresql-x64-16 >nul 2>&1
if errorlevel 1 (
    REM Try postgresql without version
    sc query postgresql >nul 2>&1
    if errorlevel 1 (
        echo [WARN] PostgreSQL service not found. Make sure PostgreSQL is installed.
        echo        Run setup-no-docker.ps1 as Administrator first.
        echo        Continuing anyway - app may fail to connect to database.
    ) else (
        net start postgresql >nul 2>&1
        echo [OK] PostgreSQL started.
    )
) else (
    sc query postgresql-x64-16 | find "RUNNING" >nul 2>&1
    if errorlevel 1 (
        echo [DB] Starting PostgreSQL service...
        net start postgresql-x64-16 >nul 2>&1
        if errorlevel 1 (
            echo [WARN] Could not start PostgreSQL. Open Services app and start it manually.
        ) else (
            echo [OK] PostgreSQL started.
        )
    ) else (
        echo [OK] PostgreSQL is already running.
    )
)

REM ── Install Python deps if missing ───────────────────────────
echo.
echo [1/3] Checking Python packages...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo      First-time install: Python packages (takes 3-5 min)...
    pip install -r "%ROOT%apps\api\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] pip install failed. Check your internet connection.
        pause
        exit /b 1
    )
    echo [OK] Python packages installed.
) else (
    echo [OK] Python packages already installed.
)

REM ── Install Node deps if missing ─────────────────────────────
echo [2/3] Checking Node.js packages...
if not exist "%ROOT%apps\web\node_modules" (
    echo      First-time install: Node packages (takes 2-3 min)...
    cd /d "%ROOT%apps\web"
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed. Check your internet connection.
        cd /d "%ROOT%"
        pause
        exit /b 1
    )
    cd /d "%ROOT%"
    echo [OK] Node packages installed.
) else (
    echo [OK] Node packages already installed.
)

REM ── Launch both servers ───────────────────────────────────────
echo [3/3] Starting servers...
echo.

start "StockLens API - port 8000" "%ROOT%apps\api\run-api.bat"
timeout /t 4 /nobreak >nul
start "StockLens Web - port 3000" "%ROOT%apps\web\run-web.bat"

echo.
echo  ================================================================
echo.
echo   StockLens is starting! Wait about 15 seconds, then open:
echo.
echo     Dashboard :  http://localhost:3000
echo     API       :  http://localhost:8000
echo     API Docs  :  http://localhost:8000/docs
echo.
echo   Two windows opened (API + Web). Keep them open while using app.
echo   Close them to stop the servers.
echo.
echo  ================================================================
echo.
pause
