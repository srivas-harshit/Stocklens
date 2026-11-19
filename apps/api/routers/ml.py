"""ML results and official stock-universe imports."""
import csv
import io
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db import AsyncSessionLocal, get_db
from models.db_models import MLClusterResult, MLScores, Stock
from services.query_service import latest_per_symbol

router = APIRouter()
log = logging.getLogger("ml_router")

CLUSTER_LABELS = [
    "QUALITY_COMPOUNDER", "DEEP_VALUE", "GARP", "CYCLICAL_RECOVERY",
    "HIGH_GROWTH_EXPENSIVE", "VALUE_TRAP", "MOMENTUM_TRAP", "DISTRESSED", "LOW_LIQUIDITY",
]


@router.get("/unlock", deprecated=True)
@router.post("/unlock")
async def unlock_db():
    raise HTTPException(status_code=501, detail="Database session termination is not available through this API.")


@router.get("/run-inference", deprecated=True)
@router.post("/run-inference")
async def run_inference():
    raise HTTPException(status_code=501, detail="On-demand ML inference is not implemented. No data was changed.")


async def import_all_nse_task():
    log.info("Starting download of full NSE equity list from official archives...")
    NSE_EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.nseindia.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
            await client.get("https://www.nseindia.com/", timeout=10)
            res = await client.get(NSE_EQUITY_LIST_URL)
            res.raise_for_status()
            content = res.text

        rows = list(csv.DictReader(io.StringIO(content)))
        log.info(f"Downloaded {len(rows)} NSE equity records. Bulk inserting...")

        async with AsyncSessionLocal() as db:
            inserted = 0
            for row in rows:
                symbol = (row.get("SYMBOL") or row.get("Symbol") or "").strip().upper()
                name = (row.get("NAME OF COMPANY") or row.get("Company Name") or "").strip()
                isin = (row.get("ISIN NUMBER") or row.get("ISIN") or "").strip()
                series = (row.get("SERIES") or row.get("Series") or "EQ").strip()
                if not symbol or not name or series not in ("EQ", "BE", "BZ", "SM", "ST"):
                    continue
                name = "".join(c for c in name if c.isalnum() or c in " .,&()-/").strip()[:200]
                symbol = "".join(c for c in symbol if c.isalnum() or c in ".-&")[:30]

                await db.execute(text("""
                    INSERT INTO stocks (id, nse_symbol, company_name, isin, instrument_type, face_value, lot_size, is_nifty50, listing_status, is_active, exchange, currency, data_source)
                    VALUES (gen_random_uuid(), :symbol, :name, :isin, 'EQ', 10.0, 1, FALSE, 'ACTIVE', TRUE, 'NSE', 'INR', 'NSE_EQUITY_LIST')
                    ON CONFLICT (nse_symbol) DO NOTHING
                """), {
                    "symbol": symbol,
                    "name": name,
                    "isin": isin[:12] if isin else None
                })
                inserted += 1
                if inserted % 200 == 0:
                    await db.commit()

            await db.commit()
            log.info(f"Successfully imported {inserted} NSE symbols into stocks table.")
    except Exception:
        log.exception("Official NSE import failed; no synthetic stocks will be generated")
        raise


@router.post("/import-all-nse", status_code=202)
async def import_all_nse(background_tasks: BackgroundTasks):
    background_tasks.add_task(import_all_nse_task)
    return {"status": "queued", "message": "Official NSE equity import started. See server logs for completion."}


@router.get("/clusters")
async def get_clusters():
    return {"clusters": CLUSTER_LABELS}


@router.get("/clusters/{label}")
async def get_cluster(label: str, db: AsyncSession = Depends(get_db)):
    label = label.upper().strip()
    if label not in CLUSTER_LABELS:
        raise HTTPException(status_code=404, detail="Unknown cluster")
    LatestCluster, latest_cluster = latest_per_symbol(MLClusterResult, MLClusterResult.run_date)
    result = await db.execute(
        select(Stock.nse_symbol, Stock.company_name, LatestCluster.run_date)
        .join(LatestCluster, and_(LatestCluster.nse_symbol == Stock.nse_symbol, latest_cluster))
        .where(Stock.is_active == True, LatestCluster.cluster_label == label)
        .order_by(Stock.nse_symbol)
    )
    return {"label": label, "stocks": [
        {"nse_symbol": row.nse_symbol, "company_name": row.company_name, "run_date": row.run_date.isoformat()}
        for row in result.all()
    ]}


@router.get("/scores/{symbol}")
async def get_scores(symbol: str, db: AsyncSession = Depends(get_db)):
    symbol = symbol.upper().strip()
    result = await db.execute(select(MLScores).where(MLScores.nse_symbol == symbol))
    scores = result.scalar_one_or_none()
    if scores is None:
        return {"symbol": symbol, "scores": None, "message": "ML scores have not been computed"}
    return {"symbol": symbol, "scores": {
        "risk_score": scores.risk_score,
        "risk_level": scores.risk_level,
        "risk_drivers": scores.risk_drivers,
        "fundamental_score": scores.fundamental_score,
        "growth_outlook_score": scores.growth_outlook_score,
        "valuation_confidence_score": scores.valuation_confidence_score,
        "valuation_confidence": scores.valuation_confidence,
        "updated_at": scores.updated_at.isoformat() if scores.updated_at else None,
    }}
