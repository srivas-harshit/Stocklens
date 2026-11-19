"""Persistent alert rules and their evaluation status."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.db import get_db
from models.db_models import Alert, Stock

router = APIRouter()
AlertType = Literal["PRICE_ABOVE", "PRICE_BELOW", "SIGNAL_CHANGE_GREEN", "SIGNAL_CHANGE_RED", "UPSIDE_PCT_ABOVE", "RISK_SCORE_ABOVE"]


class AlertCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    nse_symbol: str = Field(min_length=1, max_length=30)
    alert_type: AlertType
    condition_value: float | None = None
    condition_text: str | None = Field(None, max_length=1000)

    @field_validator("nse_symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_threshold(self):
        if not self.alert_type.startswith("SIGNAL_CHANGE_"):
            if self.condition_value is None:
                raise ValueError("A trigger value is required for this alert type")
            if self.alert_type.startswith("PRICE_") and self.condition_value <= 0:
                raise ValueError("Price thresholds must be positive")
            if self.alert_type == "RISK_SCORE_ABOVE" and not 0 <= self.condition_value <= 100:
                raise ValueError("Risk thresholds must be between 0 and 100")
        return self


class AlertUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


def serialize_alert(alert):
    return {
        "id": str(alert.id), "nse_symbol": alert.nse_symbol, "alert_type": alert.alert_type,
        "condition_value": float(alert.condition_value) if alert.condition_value is not None else None,
        "condition_text": alert.condition_text, "is_active": alert.is_active,
        "is_triggered": alert.is_triggered,
        "last_triggered": alert.last_triggered.isoformat() if alert.last_triggered else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


@router.get("")
async def get_alerts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).order_by(Alert.created_at.desc()))
    return {"alerts": [serialize_alert(alert) for alert in result.scalars().all()]}


@router.post("", status_code=201)
async def create_alert(body: AlertCreate, db: AsyncSession = Depends(get_db)):
    stock = await db.scalar(select(Stock.nse_symbol).where(Stock.nse_symbol == body.nse_symbol))
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    alert = Alert(**body.model_dump())
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return serialize_alert(alert)


@router.patch("/{alert_id}")
async def update_alert(alert_id: UUID, body: AlertUpdate, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_active = body.is_active
    await db.commit()
    return serialize_alert(alert)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
