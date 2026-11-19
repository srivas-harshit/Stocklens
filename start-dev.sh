#!/bin/bash
# StockLens Local Startup (Linux/macOS/WSL)

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   StockLens — Local Dev Startup      ║"
echo "╚══════════════════════════════════════╝"
echo ""

if [ ! -f ".env" ]; then
  echo "[ERROR] .env not found. Copy and fill in:"
  echo "  cp .env.example .env"
  exit 1
fi

echo "[1/4] Starting Redis..."
docker run -d --name stocklens-redis -p 6379:6379 redis:7-alpine 2>/dev/null || echo "Redis already running"

echo "[2/4] Starting PostgreSQL..."
docker run -d --name stocklens-db -p 5432:5432 \
  -e POSTGRES_DB=stocklens -e POSTGRES_PASSWORD=password \
  postgres:16-alpine 2>/dev/null || echo "Postgres already running"

echo "Waiting for DB to be ready..."
sleep 5

echo "[3/4] Starting FastAPI (background)..."
cd apps/api
pip install -r requirements.txt -q
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
cd ../..

echo "[4/4] Starting Next.js (background)..."
cd apps/web
npm install -q
npm run dev &
WEB_PID=$!
cd ../..

echo ""
echo "══════════════════════════════════════"
echo "StockLens running!"
echo ""
echo "  Frontend:  http://localhost:3000"
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "══════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. python scripts/import_nse_symbols.py"
echo "  2. Visit http://localhost:3000/admin"
echo ""
echo "Press Ctrl+C to stop all services..."

trap "kill $API_PID $WEB_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
