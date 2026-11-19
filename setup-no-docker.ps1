# StockLens - Setup Without Docker (Windows Native)
# Compatible with PowerShell 5.1+
# Run in PowerShell as Administrator

Write-Host ""
Write-Host "StockLens - No-Docker Windows Setup"
Write-Host "====================================="
Write-Host ""

# Check running as Admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Please run this script as Administrator." -ForegroundColor Red
    Write-Host "        Right-click PowerShell and choose 'Run as Administrator'" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Running as Administrator" -ForegroundColor Green

# Install PostgreSQL 16 via winget
Write-Host "[1/4] Installing PostgreSQL 16..." -ForegroundColor Cyan
winget install --id PostgreSQL.PostgreSQL.16 --accept-package-agreements --accept-source-agreements -e
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] winget install returned non-zero. PostgreSQL may already be installed or failed." -ForegroundColor Yellow
    Write-Host "       If not installed, download from: https://www.postgresql.org/download/windows/" -ForegroundColor Yellow
}

# Install Memurai (Redis for Windows)
Write-Host "[2/4] Installing Memurai (Redis for Windows)..." -ForegroundColor Cyan
winget install --id Memurai.Memurai --accept-package-agreements --accept-source-agreements -e
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Memurai install failed. Trying alternative..." -ForegroundColor Yellow
    Write-Host "       Download manually from: https://www.memurai.com/get-memurai" -ForegroundColor Yellow
}

# Add PostgreSQL to PATH
$pgBin = "C:\Program Files\PostgreSQL\16\bin"
if (Test-Path $pgBin) {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($currentPath -notlike "*$pgBin*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$pgBin", "Machine")
        $env:Path += ";$pgBin"
        Write-Host "[OK] Added PostgreSQL to PATH" -ForegroundColor Green
    } else {
        Write-Host "[OK] PostgreSQL already in PATH" -ForegroundColor Green
    }
} else {
    Write-Host "[WARN] PostgreSQL bin not found at $pgBin - it may still be installing" -ForegroundColor Yellow
}

# Wait for PostgreSQL service to be ready
Write-Host "[3/4] Waiting for PostgreSQL to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# Create the stocklens database
Write-Host "[4/4] Creating stocklens database..." -ForegroundColor Cyan

# Find psql path
$psqlCmd = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCmd) {
    $pgBin = Split-Path $psqlCmd.Source
} else {
    $pgBin = "C:\Program Files\PostgreSQL\16\bin"
}

$env:PGPASSWORD = "password"
$psqlExe = Join-Path $pgBin "psql.exe"

if (Test-Path $psqlExe) {
    try {
        & $psqlExe -U postgres -c "CREATE DATABASE stocklens;" 2>$null
        & $psqlExe -U postgres -c "ALTER USER postgres WITH PASSWORD 'password';" 2>$null
        & $psqlExe -U postgres -d stocklens -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>$null
        Write-Host "[OK] Database 'stocklens' created" -ForegroundColor Green
    } catch {
        Write-Host "[WARN] Could not auto-create DB. Run manually after PostgreSQL installs:" -ForegroundColor Yellow
        Write-Host "       psql -U postgres -c `"CREATE DATABASE stocklens;`"" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] psql.exe not found. PostgreSQL may need a restart to complete install." -ForegroundColor Yellow
    Write-Host "       After restarting, run: psql -U postgres -c `"CREATE DATABASE stocklens;`"" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=================================================="
Write-Host "  PostgreSQL: localhost:5432 (user: postgres / pass: password)"
Write-Host "  Redis:      localhost:6379 (via Memurai service)"
Write-Host ""
Write-Host "  NEXT STEPS:"
Write-Host "  1. Restart PowerShell (to pick up new PATH)"
Write-Host "  2. cd to stocklens folder"
Write-Host "  3. Run: pip install -r apps\api\requirements.txt"
Write-Host "  4. Run: cd apps\web && npm install"
Write-Host "  5. Start API: cd apps\api && uvicorn main:app --reload --port 8000"
Write-Host "  6. Start Web: cd apps\web && npm run dev"
Write-Host "  7. Open browser: http://localhost:3000"
Write-Host "=================================================="
