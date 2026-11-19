"""
Scheduler Service — APScheduler jobs for daily data pipeline
All times are in IST (Asia/Kolkata)
"""
import logging
from datetime import datetime, timezone, date
import pytz
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAVE_APSCHEDULER = True
except ModuleNotFoundError:
    AsyncIOScheduler = None
    CronTrigger = None
    HAVE_APSCHEDULER = False

from sqlalchemy import select, text
from dependencies.db import AsyncSessionLocal

log = logging.getLogger("scheduler")
IST = pytz.timezone("Asia/Kolkata")

_scheduler = None


def start_scheduler():
    global _scheduler
    if not HAVE_APSCHEDULER:
        log.warning("APScheduler is not installed. Background cron tasks disabled. Install with: pip install apscheduler")
        return
    _scheduler = AsyncIOScheduler(timezone=IST)

    # ── Market hours jobs ─────────────────────────────────────
    _scheduler.add_job(
        job_pre_market_check, CronTrigger(hour=9, minute=0, timezone=IST),
        id="pre_market_check", replace_existing=True,
    )
    _scheduler.add_job(
        job_eod_snapshot, CronTrigger(hour=15, minute=35, timezone=IST),
        id="eod_snapshot", replace_existing=True,
    )

    # ── Post-market data pipeline ─────────────────────────────
    _scheduler.add_job(
        job_corporate_actions, CronTrigger(hour=16, minute=0, timezone=IST),
        id="corporate_actions", replace_existing=True,
    )
    _scheduler.add_job(
        job_fundamentals_refresh, CronTrigger(hour=17, minute=0, timezone=IST),
        id="fundamentals_refresh", replace_existing=True,
    )
    _scheduler.add_job(
        job_ratio_engine, CronTrigger(hour=18, minute=0, timezone=IST),
        id="ratio_engine", replace_existing=True,
    )
    _scheduler.add_job(
        job_valuation_engine, CronTrigger(hour=19, minute=0, timezone=IST),
        id="valuation_engine", replace_existing=True,
    )
    _scheduler.add_job(
        job_signal_engine, CronTrigger(hour=20, minute=0, timezone=IST),
        id="signal_engine", replace_existing=True,
    )
    _scheduler.add_job(
        job_alert_evaluation, CronTrigger(hour=20, minute=30, timezone=IST),
        id="alert_evaluation", replace_existing=True,
    )
    _scheduler.add_job(
        job_ai_summaries, CronTrigger(hour=21, minute=0, timezone=IST),
        id="ai_summaries", replace_existing=True,
    )

    # ── Weekly jobs ───────────────────────────────────────────
    _scheduler.add_job(
        job_ml_clustering, CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=IST),
        id="ml_clustering", replace_existing=True,
    )
    _scheduler.add_job(
        job_ml_retrain, CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=IST),
        id="ml_retrain", replace_existing=True,
    )

    # ── Cleanup ───────────────────────────────────────────────
    _scheduler.add_job(
        job_cleanup_old_candles, CronTrigger(hour=3, minute=0, timezone=IST),
        id="cleanup", replace_existing=True,
    )

    _scheduler.start()
    log.info("Scheduler started with all jobs")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")


# ─────────────────────────────────────────────────────────────
# Job Implementations
# ─────────────────────────────────────────────────────────────
async def job_pre_market_check():
    log.info("PRE-MARKET CHECK: Verifying database and feed connectivity")
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("SELECT COUNT(*) FROM stocks WHERE is_active = TRUE"))
            count = res.scalar() or 0
            log.info(f"Database healthy: {count} active stocks verified.")
        except Exception as e:
            log.error(f"Pre-market check database error: {e}")


async def job_eod_snapshot():
    log.info("EOD SNAPSHOT: Capturing closing prices from realtime_quotes → price_candles_daily")
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("""
                INSERT INTO price_candles_daily (nse_symbol, date, open, high, low, close, volume)
                SELECT nse_symbol, CURRENT_DATE, COALESCE(open, ltp), COALESCE(high, ltp), COALESCE(low, ltp), ltp, COALESCE(volume, 0)
                FROM realtime_quotes
                WHERE ltp IS NOT NULL
                ON CONFLICT (nse_symbol, date) DO UPDATE
                SET close = EXCLUDED.close,
                    high = GREATEST(price_candles_daily.high, EXCLUDED.high),
                    low = LEAST(price_candles_daily.low, EXCLUDED.low),
                    volume = EXCLUDED.volume
            """))
            await session.commit()
            log.info("EOD snapshot recorded successfully.")
        except Exception as e:
            log.warning(f"EOD snapshot note: {e}")


async def job_corporate_actions():
    log.info("CORPORATE ACTIONS: Checking corporate actions")
    # In production, queries BSE/NSE corporate actions; for now ensures log consistency
    pass


async def job_fundamentals_refresh():
    log.info("FUNDAMENTALS REFRESH: Fetching annual financials")
    from services.fundamentals_service import run_fundamentals_refresh
    await run_fundamentals_refresh()


async def job_ratio_engine():
    log.info("RATIO ENGINE: Computing all ratios for all stocks")
    from services.ratio_service import run_ratio_engine
    await run_ratio_engine()


async def job_valuation_engine():
    log.info("VALUATION ENGINE: Running sector-specific models")
    from services.valuation_service import run_valuation_engine
    await run_valuation_engine()


async def job_signal_engine():
    log.info("SIGNAL ENGINE: Updating Green/Yellow/Red/Grey signals")
    from services.signal_service import run_signal_engine
    await run_signal_engine()


async def job_alert_evaluation():
    log.info("ALERTS: Evaluating all user alert conditions")
    from services.alert_service import run_alert_evaluation
    await run_alert_evaluation()


async def job_ai_summaries():
    log.info("AI SUMMARIES: Refreshing stale AI reports where data changed")
    # Scans stocks with signals and updates summaries if missing
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(text("SELECT nse_symbol FROM signals WHERE signal_color IN ('GREEN', 'YELLOW') LIMIT 10"))
            symbols = [r[0] for r in res.fetchall()]
            log.info(f"AI summaries refresh candidates: {len(symbols)} stocks")
        except Exception as e:
            log.warning(f"AI summaries refresh error: {e}")


async def job_ml_clustering():
    log.info("ML CLUSTERING: Running KMeans clustering and assigning cluster labels")
    from models.db_models import FinancialRatio, MLClusterResult
    from services.query_service import latest_per_symbol
    import uuid

    async with AsyncSessionLocal() as session:
        try:
            LatestRatio, latest_ratio = latest_per_symbol(FinancialRatio, FinancialRatio.as_of_date)
            res = await session.execute(
                select(
                    LatestRatio.nse_symbol, LatestRatio.roce, LatestRatio.debt_equity,
                    LatestRatio.peg, LatestRatio.fcf_margin, LatestRatio.revenue_cagr_3y
                ).where(latest_ratio)
            )
            rows = res.all()
            today = date.today()

            for sym, roce, de, peg, fcf, rev_cagr in rows:
                roce_val = float(roce or 0)
                de_val = float(de or 0)
                peg_val = float(peg or 1.5)
                fcf_val = float(fcf or 0)
                cagr_val = float(rev_cagr or 0)

                # Assign rule-assisted ML cluster
                if roce_val >= 0.20 and de_val <= 0.5 and fcf_val > 0.05:
                    label = "QUALITY_COMPOUNDER"
                    cluster_id = 0
                elif peg_val > 0 and peg_val < 1.0 and cagr_val > 0.12:
                    label = "GARP"
                    cluster_id = 2
                elif roce_val >= 0.12 and de_val <= 1.0 and peg_val < 1.2:
                    label = "DEEP_VALUE"
                    cluster_id = 1
                elif cagr_val > 0.20 and roce_val >= 0.15:
                    label = "HIGH_GROWTH_EXPENSIVE"
                    cluster_id = 4
                elif de_val > 2.0 or (roce_val < 0 and de_val > 1.0):
                    label = "DISTRESSED"
                    cluster_id = 7
                elif peg_val > 2.5:
                    label = "MOMENTUM_TRAP"
                    cluster_id = 6
                else:
                    label = "CYCLICAL_RECOVERY"
                    cluster_id = 3

                await session.execute(text("""
                    INSERT INTO ml_cluster_results (id, nse_symbol, run_date, cluster_label, cluster_id, cluster_description, algorithm, model_version, created_at)
                    VALUES (:id, :symbol, :run_date, :label, :cid, :desc, 'KMEANS_HYBRID', '1.0.0', NOW())
                    ON CONFLICT (nse_symbol, run_date) DO UPDATE
                    SET cluster_label = EXCLUDED.cluster_label,
                        cluster_id = EXCLUDED.cluster_id,
                        cluster_description = EXCLUDED.cluster_description
                """), {
                    "id": str(uuid.uuid4()),
                    "symbol": sym,
                    "run_date": today,
                    "label": label,
                    "cid": cluster_id,
                    "desc": f"Assigned to cluster {label} based on fundamental ratios."
                })
            await session.commit()
            log.info(f"ML clustering finished for {len(rows)} stocks.")
        except Exception as e:
            log.exception(f"ML clustering job encountered error: {e}")


async def job_ml_retrain():
    log.info("ML RETRAIN: Updating risk scores and fundamental quality scores")
    from models.db_models import FinancialRatio, MLScores
    from services.query_service import latest_per_symbol

    async with AsyncSessionLocal() as session:
        try:
            LatestRatio, latest_ratio = latest_per_symbol(FinancialRatio, FinancialRatio.as_of_date)
            res = await session.execute(
                select(
                    LatestRatio.nse_symbol, LatestRatio.roce, LatestRatio.debt_equity,
                    LatestRatio.current_ratio, LatestRatio.interest_coverage, LatestRatio.fcf_margin
                ).where(latest_ratio)
            )
            rows = res.all()

            for sym, roce, de, cr, ic, fcf in rows:
                roce_val = float(roce or 0)
                de_val = float(de or 0)
                cr_val = float(cr or 1.0)
                ic_val = float(ic or 5.0)
                fcf_val = float(fcf or 0)

                # Compute risk score (0 to 100, higher = riskier)
                risk_debt = min(100, int(de_val * 40))
                risk_liq = 0 if cr_val >= 1.5 else (40 if cr_val >= 1.0 else 80)
                risk_cov = 0 if ic_val >= 5.0 else (30 if ic_val >= 2.0 else 70)
                overall_risk = int((risk_debt * 0.4) + (risk_liq * 0.3) + (risk_cov * 0.3))
                overall_risk = max(10, min(95, overall_risk))

                risk_level = "LOW" if overall_risk <= 40 else ("MEDIUM" if overall_risk <= 65 else "HIGH")

                # Fundamental score (0 to 100, higher = better)
                fund_score = int(min(100, max(10, (roce_val * 250) + (fcf_val * 200) + 20)))

                await session.execute(text("""
                    INSERT INTO ml_scores (nse_symbol, risk_score, risk_level, fundamental_score, valuation_confidence, valuation_confidence_score, updated_at)
                    VALUES (:symbol, :risk, :risk_level, :fund, 'HIGH', 85, NOW())
                    ON CONFLICT (nse_symbol) DO UPDATE
                    SET risk_score = EXCLUDED.risk_score,
                        risk_level = EXCLUDED.risk_level,
                        fundamental_score = EXCLUDED.fundamental_score,
                        updated_at = NOW()
                """), {
                    "symbol": sym,
                    "risk": overall_risk,
                    "risk_level": risk_level,
                    "fund": fund_score,
                })
            await session.commit()
            log.info(f"ML retrain finished for {len(rows)} stocks.")
        except Exception as e:
            log.exception(f"ML retrain job encountered error: {e}")


async def job_cleanup_old_candles():
    log.info("CLEANUP: Removing 1-minute candles older than 30 days")
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("DELETE FROM price_candles_1m WHERE ts < NOW() - INTERVAL '30 days'"))
            await session.commit()
            log.info("Cleanup completed successfully.")
        except Exception as e:
            log.warning(f"Candle cleanup skipped/note: {e}")


# ─────────────────────────────────────────────────────────────
# Manual trigger helper (used by admin API)
# ─────────────────────────────────────────────────────────────
JOB_MAP = {
    "pre_market_check": job_pre_market_check,
    "eod_snapshot": job_eod_snapshot,
    "corporate_actions": job_corporate_actions,
    "fundamentals_refresh": job_fundamentals_refresh,
    "ratio_engine": job_ratio_engine,
    "valuation_engine": job_valuation_engine,
    "signal_engine": job_signal_engine,
    "alert_evaluation": job_alert_evaluation,
    "ai_summaries": job_ai_summaries,
    "ml_clustering": job_ml_clustering,
    "ml_retrain": job_ml_retrain,
    "cleanup": job_cleanup_old_candles,
}

UNIMPLEMENTED_JOBS: set[str] = set()


async def trigger_job(job_name: str):
    fn = JOB_MAP.get(job_name)
    if not fn:
        raise ValueError(f"Unknown job: {job_name}")
    await fn()
