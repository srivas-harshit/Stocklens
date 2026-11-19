# StockLens — NSE Stock Intelligence Platform

> Personal stock research and intelligence platform. Local-only. No login required.

## Quick Start (Windows)

```powershell
# 1. Copy env template and fill your keys
copy .env.example .env
notepad .env     # fill in your API keys

# 2. Start infrastructure (PostgreSQL + Redis + pgAdmin)
docker compose up -d postgres redis pgadmin

# 3. Run first-time setup (installs deps + migrations + seeds)
.\setup-first-time.bat

# 4. Start dev servers
.\start-dev.bat

# 5. Open browser
# http://localhost:3000   → Dashboard
# http://localhost:5050   → pgAdmin (DB viewer)
# http://localhost:8000/docs → FastAPI Swagger
```

> **Note:** Modern Docker Desktop uses `docker compose` (space), not `docker-compose` (hyphen).
> If you see `docker-compose not recognized`, use `docker compose` instead.

## Stack
- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: Python FastAPI
- **Worker**: Python Upstox WebSocket ingestor
- **ML**: scikit-learn + XGBoost + LightGBM + pandas
- **AI**: Google Gemini Flash 1.5
- **Database**: PostgreSQL 16 + pgvector
- **Cache**: Redis 7

## Keys You Need
1. **Upstox API Key** → [developer.upstox.com](https://developer.upstox.com)
2. **Google Gemini API Key** → [aistudio.google.com](https://aistudio.google.com) (free)

## Services
| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| FastAPI docs | http://localhost:8000/docs |
| WebSocket | ws://localhost:8001 |
| pgAdmin | http://localhost:5050 |
| Redis | localhost:6379 |

## Important
- This is a personal research tool, not investment advice
- Real-time data via Upstox API (read-only)
- Never commit your `.env` file
