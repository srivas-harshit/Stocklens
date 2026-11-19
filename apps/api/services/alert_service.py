"""Evaluate persisted alert rules without accepting synthetic or stale quotes."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from dependencies.db import AsyncSessionLocal
from models.db_models import Alert, IntrinsicValue, MLScores, RealtimeQuote, Signal

log = logging.getLogger("alert_service")


def should_trigger(alert, quote=None, signal=None, valuation=None, scores=None):
    threshold = float(alert.condition_value) if alert.condition_value is not None else None
    if alert.alert_type in ("PRICE_ABOVE", "PRICE_BELOW"):
        if (quote is None or quote.ltp is None or quote.ltp <= 0 or quote.is_stale
                or quote.data_source in ("MOCK", "SEED", "DEV_SEED") or threshold is None):
            return False
        price = float(quote.ltp)
        return price >= threshold if alert.alert_type == "PRICE_ABOVE" else price <= threshold
    if alert.alert_type == "UPSIDE_PCT_ABOVE":
        return (valuation is not None and valuation.upside_pct is not None
                and threshold is not None and float(valuation.upside_pct) >= threshold)
    if alert.alert_type == "RISK_SCORE_ABOVE":
        return (scores is not None and scores.risk_score is not None
                and threshold is not None and scores.risk_score >= threshold)
    if alert.alert_type in ("SIGNAL_CHANGE_GREEN", "SIGNAL_CHANGE_RED"):
        expected = alert.alert_type.removeprefix("SIGNAL_CHANGE_")
        if (signal is None or signal.signal_color != expected or signal.prev_signal_color == expected
                or signal.signal_changed_at is None or alert.created_at is None
                or signal.data_freshness in ("MOCK", "SEED", "DEV_SEED")):
            return False
        changed = signal.signal_changed_at
        created = alert.created_at
        if changed.tzinfo is None:
            changed = changed.replace(tzinfo=timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return changed >= created
    return False


async def run_alert_evaluation():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Alert).where(Alert.is_active == True, Alert.is_triggered == False))
        alerts = result.scalars().all()
        triggered = 0
        for alert in alerts:
            context = {}
            if alert.alert_type.startswith("PRICE_"):
                context["quote"] = await db.get(RealtimeQuote, alert.nse_symbol)
            elif alert.alert_type.startswith("SIGNAL_CHANGE_"):
                context["signal"] = await db.get(Signal, alert.nse_symbol)
            elif alert.alert_type == "UPSIDE_PCT_ABOVE":
                context["valuation"] = await db.get(IntrinsicValue, alert.nse_symbol)
            elif alert.alert_type == "RISK_SCORE_ABOVE":
                context["scores"] = await db.get(MLScores, alert.nse_symbol)
            if should_trigger(alert, **context):
                alert.is_triggered = True
                alert.last_triggered = datetime.now(timezone.utc)
                triggered += 1
        await db.commit()
        log.info("Alerts evaluated: triggered=%s/%s", triggered, len(alerts))
