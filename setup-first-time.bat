@echo off
REM ══════════════════════════════════════════════════════════════════
REM StockLens — First-Time Setup Wizard (Windows)
REM Supports both Docker and no-Docker setups
REM ══════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion
set ROOT=%~dp0
cd /d "%ROOT%"

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║      StockLens — First-Time Setup Wizard         ║
echo ╚══════════════════════════════════════════════════╝
echo.

REM ── Check .env ───────────────────────────────────────────
if not exist ".env" (
    echo Copying .env.example to .env ...
    copy .env.example .env >nul
    echo.
    echo !! IMPORTANT: Edit .env and fill in your API keys !!
    echo    - UPSTOX_API_KEY and UPSTOX_API_SECRET
    echo    - GEMINI_API_KEY (free at aistudio.google.com)
    echo.
    notepad .env
    echo Press any key once you have saved your .env file...
    pause >nul
)

REM ── Detect Docker ────────────────────────────────────────
docker --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] Docker is NOT installed on this machine.
    echo.
    echo     You have two options:
    echo.
    echo     OPTION A ^(Recommended^): Install Docker Desktop
    echo       Download from: https://docs.docker.com/desktop/install/windows-install/
    echo       After install, restart this script.
    echo.
    echo     OPTION B: Install PostgreSQL + Redis natively ^(no Docker^)
    echo       Right-click PowerShell as Administrator, then run:
    echo       powershell -ExecutionPolicy Bypass -File setup-no-docker.ps1
    echo       After that, restart this script.
    echo.
    echo     Opening Docker Desktop download page in browser...
    start https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

REM ── Detect Docker Compose mode (v1 vs v2) ────────────────
set DOCKER_COMPOSE=docker compose
docker compose version >nul 2>&1
if errorlevel 1 (
    REM Fallback: try old docker-compose binary
    docker-compose --version >nul 2>&1
    if not errorlevel 1 (
        set DOCKER_COMPOSE=docker-compose
        echo [INFO] Using legacy docker-compose binary.
    ) else (
        echo [ERROR] Docker Compose not found. Update Docker Desktop.
        pause
        exit /b 1
    )
)
echo [OK] Docker is ready. Using: %DOCKER_COMPOSE%

REM ── Start infrastructure ──────────────────────────────────
echo [1/6] Starting PostgreSQL + Redis + pgAdmin...
%DOCKER_COMPOSE% up -d postgres redis pgadmin
if errorlevel 1 (
    echo [ERROR] Docker failed to start services. Check Docker Desktop is running.
    pause
    exit /b 1
)
echo Waiting 10 seconds for PostgreSQL to be ready...
timeout /t 10 /nobreak >nul

REM ── Install Python deps ───────────────────────────────────
echo [2/6] Installing Python dependencies...
cd /d "%ROOT%apps\api"
pip install -r requirements.txt -q
cd /d "%ROOT%"

REM ── Install Node deps ─────────────────────────────────────
echo [3/6] Installing Node.js dependencies...
cd /d "%ROOT%apps\web"
call npm install --silent
cd /d "%ROOT%"

REM ── Run database migrations ───────────────────────────────
echo [4/6] Running database migrations...
cd /d "%ROOT%apps\api"
echo import asyncio, asyncpg, os, sys > .tmp_migrate.py
echo from dotenv import load_dotenv >> .tmp_migrate.py
echo load_dotenv('../../.env') >> .tmp_migrate.py
echo db_url = os.getenv('DATABASE_SYNC_URL') or 'postgresql://postgres:password@localhost:5432/stocklens' >> .tmp_migrate.py
echo db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://').replace('postgresql+psycopg2://', 'postgresql://') >> .tmp_migrate.py
echo async def run(): >> .tmp_migrate.py
echo     try: >> .tmp_migrate.py
echo         conn = await asyncpg.connect(db_url) >> .tmp_migrate.py
echo         for f in ['001_initial.sql', '002_pgvector_fo_peers.sql']: >> .tmp_migrate.py
echo             path = f'../../supabase/migrations/{f}' >> .tmp_migrate.py
echo             try: >> .tmp_migrate.py
echo                 with open(path) as fp: sql = fp.read() >> .tmp_migrate.py
echo                 await conn.execute(sql) >> .tmp_migrate.py
echo                 print(f'[OK] Migration {f} applied') >> .tmp_migrate.py
echo             except FileNotFoundError: >> .tmp_migrate.py
echo                 print(f'[SKIP] {f} not found') >> .tmp_migrate.py
echo             except Exception as e: >> .tmp_migrate.py
echo                 print(f'[WARN] {f}: {e}') >> .tmp_migrate.py
echo         await conn.close() >> .tmp_migrate.py
echo     except Exception as e: >> .tmp_migrate.py
echo         print(f'[ERROR] DB connection failed: {e}') >> .tmp_migrate.py
echo         print('  Check: docker compose ps   to see if postgres is running') >> .tmp_migrate.py
echo asyncio.run(run()) >> .tmp_migrate.py
python .tmp_migrate.py
del .tmp_migrate.py
cd /d "%ROOT%"

REM ── Seed dev data ─────────────────────────────────────────
echo [5/6] Seeding development data (20 Nifty50 demo stocks)...
python scripts\seed_dev_data.py

REM ── Seed sectors ──────────────────────────────────────────
echo [6/6] Seeding sector classifications...
python scripts\seed_sectors.py

echo.
echo ══════════════════════════════════════════════════════════════
echo  Setup Complete!
echo.
echo  Now run:  .\start-dev.bat
echo  Then open: http://localhost:3000
echo ══════════════════════════════════════════════════════════════
echo.
pause
