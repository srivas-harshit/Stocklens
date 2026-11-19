import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from dependencies.db import get_db
from models.db_models import (
    Portfolio, PortfolioHolding, Stock, SectorClassification,
    RealtimeQuote, IntrinsicValue, MLScores, Signal
)

router = APIRouter()


@router.get("")
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Portfolio).limit(1))
    portfolio = r.scalar_one_or_none()
    if not portfolio:
        return {"portfolio": None, "holdings": []}
    h = await db.execute(
        select(PortfolioHolding)
        .where(PortfolioHolding.portfolio_id == portfolio.id)
        .order_by(PortfolioHolding.created_at.desc())
    )
    holdings = h.scalars().all()
    return {
        "portfolio": {"id": str(portfolio.id), "name": portfolio.name},
        "holdings": [
            {
                "id": str(holding.id),
                "nse_symbol": holding.nse_symbol,
                "quantity": float(holding.quantity),
                "avg_cost": float(holding.avg_cost),
                "buy_date": holding.buy_date.isoformat() if holding.buy_date else None,
            }
            for holding in holdings
        ],
    }


@router.post("/holdings", status_code=201)
async def add_holding(body: dict, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Portfolio).limit(1))
    portfolio = r.scalar_one_or_none()
    if not portfolio:
        portfolio = Portfolio(name="My Portfolio")
        db.add(portfolio)
        await db.flush()

    symbol = body.get("nse_symbol", "").upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Stock symbol is required")

    try:
        qty = float(body["quantity"])
        cost = float(body["avg_cost"])
        if qty <= 0 or cost <= 0:
            raise ValueError
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Quantity and avg_cost must be positive numbers")

    buy_date = None
    if body.get("buy_date"):
        try:
            buy_date = date.fromisoformat(body["buy_date"])
        except ValueError:
            pass

    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        nse_symbol=symbol,
        quantity=qty,
        avg_cost=cost,
        buy_date=buy_date,
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return {"id": str(holding.id), "nse_symbol": holding.nse_symbol}


@router.patch("/holdings/{holding_id}")
async def update_holding(holding_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    try:
        h_uuid = uuid.UUID(holding_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid holding ID format")

    h = await db.get(PortfolioHolding, h_uuid)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")

    if "quantity" in body:
        try:
            qty = float(body["quantity"])
            if qty <= 0:
                raise ValueError
            h.quantity = qty
        except ValueError:
            raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    if "avg_cost" in body:
        try:
            cost = float(body["avg_cost"])
            if cost <= 0:
                raise ValueError
            h.avg_cost = cost
        except ValueError:
            raise HTTPException(status_code=400, detail="Avg cost must be greater than zero")

    if "buy_date" in body:
        if body["buy_date"]:
            try:
                h.buy_date = date.fromisoformat(body["buy_date"])
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
        else:
            h.buy_date = None

    await db.commit()
    await db.refresh(h)
    return {
        "id": str(h.id),
        "nse_symbol": h.nse_symbol,
        "quantity": float(h.quantity),
        "avg_cost": float(h.avg_cost),
        "buy_date": h.buy_date.isoformat() if h.buy_date else None,
    }


@router.delete("/holdings/{holding_id}", status_code=204)
async def delete_holding(holding_id: str, db: AsyncSession = Depends(get_db)):
    try:
        h_uuid = uuid.UUID(holding_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid holding ID format")

    result = await db.execute(delete(PortfolioHolding).where(PortfolioHolding.id == h_uuid))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Holding not found")


@router.get("/analytics")
async def get_portfolio_analytics(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Portfolio).limit(1))
    portfolio = r.scalar_one_or_none()
    if not portfolio:
        return {"analytics": None, "message": "No portfolio found"}

    h_res = await db.execute(
        select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id)
    )
    holdings = h_res.scalars().all()
    if not holdings:
        return {
            "analytics": {
                "total_invested": 0.0,
                "total_current_value": 0.0,
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
                "holdings_count": 0,
                "sector_breakdown": [],
                "top_performers": [],
                "weighted_upside_pct": None,
                "weighted_risk_score": None,
            },
            "message": "Portfolio is empty",
        }

    total_invested = 0.0
    total_current_value = 0.0
    sector_invested: dict[str, float] = {}
    performers = []
    total_weighted_upside = 0.0
    total_upside_weight = 0.0
    total_weighted_risk = 0.0
    total_risk_weight = 0.0

    for h in holdings:
        cost = float(h.avg_cost) * float(h.quantity)
        total_invested += cost

        # Fetch current price
        q_res = await db.execute(
            select(RealtimeQuote.ltp).where(RealtimeQuote.nse_symbol == h.nse_symbol)
        )
        ltp = q_res.scalar_one_or_none()
        current_val = (float(ltp) * float(h.quantity)) if ltp else cost
        total_current_value += current_val

        pnl = current_val - cost
        pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0

        # Sector
        sec_res = await db.execute(
            select(SectorClassification.sector)
            .join(Stock, Stock.sector_id == SectorClassification.id)
            .where(Stock.nse_symbol == h.nse_symbol)
        )
        sector_name = sec_res.scalar_one_or_none() or "Unclassified"
        sector_invested[sector_name] = sector_invested.get(sector_name, 0.0) + current_val

        # Upside
        iv_res = await db.execute(
            select(IntrinsicValue.upside_pct).where(IntrinsicValue.nse_symbol == h.nse_symbol)
        )
        upside = iv_res.scalar_one_or_none()
        if upside is not None:
            total_weighted_upside += float(upside) * current_val
            total_upside_weight += current_val

        # Risk
        ml_res = await db.execute(
            select(MLScores.risk_score).where(MLScores.nse_symbol == h.nse_symbol)
        )
        risk = ml_res.scalar_one_or_none()
        if risk is not None:
            total_weighted_risk += float(risk) * current_val
            total_risk_weight += current_val

        performers.append({
            "symbol": h.nse_symbol,
            "invested": round(cost, 2),
            "current_value": round(current_val, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    total_pnl = total_current_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested > 0 else 0.0

    sector_breakdown = [
        {
            "sector": sec,
            "current_value": round(val, 2),
            "allocation_pct": round((val / total_current_value * 100.0) if total_current_value > 0 else 0.0, 2),
        }
        for sec, val in sorted(sector_invested.items(), key=lambda x: x[1], reverse=True)
    ]

    performers.sort(key=lambda x: x["pnl_pct"], reverse=True)

    return {
        "analytics": {
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current_value, 2),
            "unrealized_pnl": round(total_pnl, 2),
            "unrealized_pnl_pct": round(total_pnl_pct, 2),
            "holdings_count": len(holdings),
            "sector_breakdown": sector_breakdown,
            "top_performers": performers[:5],
            "weighted_upside_pct": round(total_weighted_upside / total_upside_weight, 2) if total_upside_weight > 0 else None,
            "weighted_risk_score": round(total_weighted_risk / total_risk_weight, 1) if total_risk_weight > 0 else None,
        }
    }
