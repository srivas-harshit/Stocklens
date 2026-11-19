"""
Admin Router — data import, job triggers, audit logs
No auth needed — local-only app, direct access
"""
import os
import uuid
import csv
import io
from datetime import datetime, timezone, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from dependencies.db import AsyncSessionLocal, get_db
from models.db_models import DataImportLog, AuditLog, SystemJob, AdminOverride, Stock, FinancialResult
from config import settings
import logging

router = APIRouter()
log = logging.getLogger("admin")


@router.get("/jobs")
async def list_jobs(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(SystemJob).order_by(SystemJob.created_at.desc()).limit(50))
    jobs = r.scalars().all()
    return {
        "jobs": [
            {
                "id": str(j.id),
                "job_name": j.job_name,
                "status": j.status,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "duration_ms": j.duration_ms,
                "stocks_processed": j.stocks_processed,
                "triggered_by": j.triggered_by,
            }
            for j in jobs
        ]
    }


@router.post("/jobs/trigger/{job_name}")
async def trigger_job(job_name: str, db: AsyncSession = Depends(get_db)):
    from services.scheduler_service import trigger_job as _trigger, JOB_MAP, UNIMPLEMENTED_JOBS
    import asyncio

    if job_name in UNIMPLEMENTED_JOBS:
        raise HTTPException(status_code=501, detail=f"Job '{job_name}' is not implemented. No job was queued.")
    if job_name not in JOB_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown job. Valid: {list(JOB_MAP)}")

    job = SystemJob(
        job_name=job_name,
        status="RUNNING",
        triggered_by="MANUAL",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    job_id = job.id

    async def run_and_update():
        start = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            try:
                await _trigger(job_name)
                elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
                await session.execute(
                    text(
                        "UPDATE system_jobs SET status='COMPLETED', completed_at=NOW(), duration_ms=:ms WHERE id=:id"
                    ),
                    {"ms": elapsed, "id": str(job_id)},
                )
                await session.commit()
            except Exception as e:
                log.error(f"Job {job_name} failed: {e}")
                await session.rollback()
                await session.execute(
                    text(
                        "UPDATE system_jobs SET status='FAILED', completed_at=NOW() WHERE id=:id"
                    ),
                    {"id": str(job_id)},
                )
                await session.commit()

    asyncio.create_task(run_and_update())
    return {"message": f"Job '{job_name}' triggered", "job_id": str(job_id)}


@router.get("/audit-logs")
async def get_audit_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    logs = r.scalars().all()
    return {
        "logs": [
            {
                "id": str(l.id),
                "action": l.action,
                "entity_type": l.entity_type,
                "status": l.status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    }


@router.get("/import-logs")
async def get_import_logs(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(DataImportLog).order_by(DataImportLog.started_at.desc()).limit(50))
    logs = r.scalars().all()
    return {
        "logs": [
            {
                "id": str(l.id),
                "import_type": l.import_type,
                "filename": l.filename,
                "records_total": l.records_total,
                "records_success": l.records_success,
                "records_failed": l.records_failed,
                "status": l.status,
                "started_at": l.started_at.isoformat() if l.started_at else None,
            }
            for l in logs
        ]
    }


@router.post("/financials/upload")
async def upload_financials(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload financials CSV/Excel to populate financial_results."""
    content = await file.read()
    filename = file.filename or "financials.csv"
    import_log = DataImportLog(
        import_type="FINANCIALS",
        filename=filename,
        source="UPLOAD",
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db.add(import_log)
    await db.commit()
    await db.refresh(import_log)

    success_count = 0
    failed_count = 0
    errors = []

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content))
            records = df.to_dict(orient="records")
        else:
            text_data = content.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text_data))
            records = list(reader)

        for row in records:
            try:
                # Handle various column name styles
                sym = (row.get("symbol") or row.get("SYMBOL") or row.get("nse_symbol") or "").strip().upper()
                if not sym:
                    continue

                raw_period = str(row.get("period_end") or row.get("date") or row.get("year") or "").strip()
                if not raw_period:
                    continue
                try:
                    if len(raw_period) == 4 and raw_period.isdigit():
                        period_date = date(int(raw_period), 3, 31)
                    else:
                        period_date = date.fromisoformat(raw_period[:10])
                except Exception:
                    period_date = date(2024, 3, 31)

                def parse_num(key):
                    v = row.get(key)
                    if v is None or v == "" or v == "—" or v == "-":
                        return None
                    try:
                        return float(str(v).replace(",", "").replace("%", ""))
                    except ValueError:
                        return None

                rev = parse_num("revenue") or parse_num("Sales") or parse_num("Net Sales")
                ebitda = parse_num("ebitda") or parse_num("Operating Profit")
                pat = parse_num("pat") or parse_num("Net Profit")
                eps = parse_num("eps") or parse_num("EPS in Rs")
                debt = parse_num("total_debt") or parse_num("Borrowings")
                cash = parse_num("cash_and_equiv") or parse_num("Cash Equivalents")
                cfo = parse_num("cfo") or parse_num("Cash from Operating Activity")

                await db.execute(text("""
                    INSERT INTO financial_results (
                        id, nse_symbol, period_end, period_type, revenue, ebitda, pat, eps,
                        total_debt, cash_and_equiv, cfo, data_source, created_at
                    ) VALUES (
                        gen_random_uuid(), :sym, :period_end, 'A', :rev, :ebitda, :pat, :eps,
                        :debt, :cash, :cfo, 'UPLOAD', NOW()
                    )
                    ON CONFLICT (nse_symbol, period_end, period_type) DO UPDATE
                    SET revenue = EXCLUDED.revenue,
                        ebitda = EXCLUDED.ebitda,
                        pat = EXCLUDED.pat,
                        eps = EXCLUDED.eps,
                        total_debt = EXCLUDED.total_debt,
                        cash_and_equiv = EXCLUDED.cash_and_equiv,
                        cfo = EXCLUDED.cfo
                """), {
                    "sym": sym,
                    "period_end": period_date,
                    "rev": rev,
                    "ebitda": ebitda,
                    "pat": pat,
                    "eps": eps,
                    "debt": debt,
                    "cash": cash,
                    "cfo": cfo,
                })
                success_count += 1
            except Exception as e:
                failed_count += 1
                if len(errors) < 10:
                    errors.append(str(e))

        import_log.records_total = len(records)
        import_log.records_success = success_count
        import_log.records_failed = failed_count
        import_log.errors = errors
        import_log.status = "COMPLETED"
        import_log.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "import_id": str(import_log.id),
            "status": "COMPLETED",
            "records_total": len(records),
            "records_success": success_count,
            "records_failed": failed_count,
        }
    except Exception as e:
        log.exception(f"Financial upload error: {e}")
        import_log.status = "FAILED"
        import_log.errors = [str(e)]
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to parse financials: {str(e)}")


@router.post("/stocks/import")
async def import_stocks(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload NSE EQUITY_L.csv to populate or update the stocks universe."""
    content = await file.read()
    filename = file.filename or "EQUITY_L.csv"
    import_log = DataImportLog(
        import_type="EQUITY_L",
        filename=filename,
        source="UPLOAD",
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db.add(import_log)
    await db.commit()
    await db.refresh(import_log)

    success_count = 0
    failed_count = 0
    errors = []

    try:
        text_data = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text_data))
        rows = list(reader)

        for row in rows:
            try:
                symbol = (row.get("SYMBOL") or row.get("Symbol") or row.get("symbol") or "").strip().upper()
                name = (row.get("NAME OF COMPANY") or row.get("Company Name") or row.get("company_name") or "").strip()
                isin = (row.get("ISIN NUMBER") or row.get("ISIN") or row.get("isin") or "").strip()
                series = (row.get("SERIES") or row.get("Series") or "EQ").strip()

                if not symbol or not name or series not in ("EQ", "BE", "BZ", "SM", "ST"):
                    continue

                clean_name = "".join(c for c in name if c.isalnum() or c in " .,&()-/").strip()[:200]
                clean_symbol = "".join(c for c in symbol if c.isalnum() or c in ".-&")[:30]

                await db.execute(text("""
                    INSERT INTO stocks (
                        id, nse_symbol, company_name, isin, instrument_type, face_value, lot_size,
                        is_nifty50, listing_status, is_active, exchange, currency, data_source
                    ) VALUES (
                        gen_random_uuid(), :symbol, :name, :isin, 'EQ', 10.0, 1,
                        FALSE, 'ACTIVE', TRUE, 'NSE', 'INR', 'FILE_UPLOAD'
                    )
                    ON CONFLICT (nse_symbol) DO UPDATE
                    SET company_name = EXCLUDED.company_name,
                        isin = COALESCE(EXCLUDED.isin, stocks.isin),
                        is_active = TRUE
                """), {
                    "symbol": clean_symbol,
                    "name": clean_name,
                    "isin": isin[:12] if isin else None,
                })
                success_count += 1
            except Exception as e:
                failed_count += 1
                if len(errors) < 10:
                    errors.append(str(e))

        await db.commit()

        import_log.records_total = len(rows)
        import_log.records_success = success_count
        import_log.records_failed = failed_count
        import_log.errors = errors
        import_log.status = "COMPLETED"
        import_log.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "import_id": str(import_log.id),
            "status": "COMPLETED",
            "records_total": len(rows),
            "records_success": success_count,
            "records_failed": failed_count,
        }
    except Exception as e:
        log.exception(f"Stock import error: {e}")
        import_log.status = "FAILED"
        import_log.errors = [str(e)]
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to import stocks: {str(e)}")


@router.post("/override/{table_name}/{record_id}")
async def admin_override(
    table_name: str,
    record_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Manual data correction with full audit trail."""
    allowed_tables = {"financial_results", "financial_ratios", "valuation_assumptions"}
    if table_name not in allowed_tables:
        raise HTTPException(status_code=400, detail=f"Override not allowed for table: {table_name}")

    reason = str(body.get("reason", "")).strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Reason is required for data override")

    override = AdminOverride(
        table_name=table_name,
        record_id=record_id,
        field_name=str(body.get("field_name", "")),
        old_value=str(body.get("old_value", "")),
        new_value=str(body.get("new_value", "")),
        reason=reason[:1000],
    )
    db.add(override)

    # Also log to audit_logs
    audit = AuditLog(
        action="ADMIN_OVERRIDE",
        entity_type=table_name,
        entity_id=record_id,
        details={"field": body.get("field_name"), "reason": reason},
    )
    db.add(audit)
    await db.commit()

    return {"override_id": str(override.id), "status": "RECORDED"}
