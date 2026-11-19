# StockLens — NSE Stock Intelligence Platform

> Personal stock research and intelligence platform. Local-only. No login required.

> **Full-stack quantitative research & stock valuation platform for Indian (NSE/BSE) and global equities.**  
> Built with FastAPI, Next.js 15 App Router, PostgreSQL, Redis, Scikit-Learn/XGBoost, and Google Gemini AI.

---

## 🌟 Key Features

- **Multi-Model Intrinsic Valuation**: Automated DCF (Discounted Cash Flow), PB-ROE, and EV/EBITDA models delivering Bear, Base, and Bull valuation bands with Margin of Safety markers.
- **Deep Financial Ratio Engine**: 27+ computed metrics including 3Y/5Y EPS & Revenue CAGRs, 3Y Margin Expansion, Debt/EBITDA, Net Debt/Equity, FCF Margins, and Cash Conversion (CFO/PAT).
- **ML Clustering & Risk Scoring**: Unsupervised K-Means peer clustering (*Quality Compounders*, *Deep Value*, *GARP*, *Value Traps*) and risk scoring powered by XGBoost & LightGBM.
- **Interactive Daily Price Charts**: High-performance SVG candlestick charts with multi-timeframe aggregations (1D, 1W, 1M) and volume bars.
- **Actionable Signal Engine**: Algorithmic green/yellow/red signal classifications based on financial health, valuation headroom, and risk flag gates.
- **AI Research Summaries**: Instant executive fundamental analysis powered by Google Gemini AI.

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Radix UI, Lucide Icons, SWR |
| **Backend** | Python FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, APScheduler |
| **Database & Cache** | PostgreSQL 16 (with pgvector / `real[]` fallback), Redis 7 |
| **Machine Learning** | scikit-learn, XGBoost, LightGBM, Pandas, NumPy |
| **AI Integration** | Google Gemini (via `google-genai` SDK) |
| **Market Data** | Upstox WebSocket Ingestor, Yahoo Finance (`yfinance`), NSE Bhavcopy |

---

## 📋 Prerequisites

Before starting, make sure you have the following installed on your machine:
- **Python 3.11, 3.12, or 3.13**: [Download Python](https://www.python.org/downloads/)
- **Node.js 18+ or 20+** (includes `npm`): [Download Node.js](https://nodejs.org/)
- **Docker Desktop** (recommended for PostgreSQL + Redis) or native local installations.
- **Git**

---

## 🚀 Step-by-Step Setup Guide

### 1. Clone & Configure Environment

```bash
git clone https://github.com/srivas-harshit/Stocklens.git
cd Stocklens
```

Copy the environment file template:
```powershell
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Open `.env` in your text editor. The default database and Redis values work out-of-the-box:
```env
# Database & Redis (default local credentials)
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/stocklens
DATABASE_SYNC_URL=postgresql://postgres:password@localhost:5432/stocklens
REDIS_URL=redis://localhost:6379/0

# Optional: Google Gemini AI (free key from aistudio.google.com)
GEMINI_API_KEY=your_gemini_key_here

# Optional: Upstox credentials (only needed for live trading hour streaming)
UPSTOX_API_KEY=your_upstox_key_here
UPSTOX_ACCESS_TOKEN=your_token_here
```

---

### 2. Start PostgreSQL & Redis

#### Option A: Using Docker (Recommended)
```bash
docker compose up -d postgres redis
```
*(Optional: add `pgadmin` to the command to run the browser-based DB viewer at `http://localhost:5050`)*

#### Option B: Using Native Local Services
If running PostgreSQL natively:
1. Ensure the PostgreSQL service is active on port `5432`.
2. Create the `stocklens` database in `psql`:
   ```sql
   CREATE DATABASE stocklens;
   ```
3. Ensure local Redis is running on port `6379`.

---

### 3. Install Python Dependencies

From the project root:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# (Windows Command Prompt: .venv\Scripts\activate.bat)
# (Linux / macOS: source .venv/bin/activate)

# Install API dependencies
pip install -r apps/api/requirements.txt
```

---

### 4. Apply Database Migrations

Run the automated migration runner (handles table creation, partitions, indexes, and pgvector fallback):

```bash
python scripts/apply_migrations.py
```
*Output should conclude with `All migrations applied.`*

---

### 5. Seed Historical Market & Fundamental Data

Populate the database with stock profiles, 90-day daily OHLCV price candles, financial ratios, intrinsic DCF values, and ML clusters:

```bash
# Seed all 500+ stocks in the universe
python scripts/seed_all_stocks_dev.py
```
*(Tip: For a quick 10-second seed of 14 core Nifty 50 stocks, you can run `python scripts/seed_dev_data.py --force`).*

---

### 6. Start the Backend API

In your terminal (with `.venv` active):

```powershell
cd apps\api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

### 7. Start the Frontend Web App

Open a **new terminal window** in the project root:

```powershell
cd apps\web
npm install
npm run dev
```

- **Web Dashboard:** [http://localhost:3000](http://localhost:3000)

---

## 🎯 Verification Checklist

1. Open **[http://localhost:3000](http://localhost:3000)** in your browser.
2. Search for any stock like **`TCS`**, **`RELIANCE`**, **`INFY`**, or **`HDFCBANK`**.
3. Verify on the stock page:
   - **Candlestick Chart**: 90-day daily OHLCV price action with interval toggles (1D, 1W, 1M).
   - **Valuation Range**: Bear, Base, and Bull Intrinsic Value vs CMP marker.
   - **Financial Ratios**: Growth (`EPS CAGR 3Y`, `Revenue 1Y`, `Margin Expansion 3Y`) and Leverage (`Debt/EBITDA`, `FCF Margin`).
   - **Machine Learning**: Fundamental, Growth, and Risk score gauges.

---

## 📂 Project Directory Structure

```text
Stocklens/
├── apps/
│   ├── api/             # FastAPI backend (routers, models, services)
│   ├── web/             # Next.js 15 frontend (App Router, components, SWR)
│   ├── ml/              # Scikit-Learn/XGBoost clustering & risk pipelines
│   └── worker/          # Upstox WebSocket live tick ingestion worker
├── scripts/
│   ├── apply_migrations.py      # Migration runner (handles pgvector & partitions)
│   ├── seed_all_stocks_dev.py   # Full universe dev seeder with candles & ratios
│   ├── seed_dev_data.py         # Curated Nifty sample stock seeder
│   └── fetch_live_prices.py     # Live market price synchronization
├── supabase/
│   └── migrations/      # Version-controlled SQL migration scripts
├── docker-compose.yml   # PostgreSQL + Redis + pgAdmin container specs
├── .env.example         # Environment template
└── README.md            # Project documentation
```

---

## ⚙️ Advanced Services & Tools

| Task | Command | Purpose |
|---|---|---|
| **ML Retrain Pipeline** | `python apps/ml/pipeline.py` | Runs clustering & risk model inference across the active universe. |
| **Live Upstox Streaming** | `cd apps/worker && python upstox_ws.py` | Ingests real-time tick-by-tick websocket data into Redis & Postgres. |
| **pgAdmin DB Viewer** | `docker compose up -d pgadmin` | Web UI at `http://localhost:5050` (`admin@local.com` / `admin`). |

---

## ⚠️ Disclaimer

> StockLens is a **personal financial intelligence and research tool**. All intrinsic valuations, ML risk scores, and signals are algorithmically derived from historical financials and mathematical assumptions. None of the content represents investment or trading advice. Verify all data independently before making investment decisions.

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
