"""Unit tests for offline financial engines, ratios, and logic."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from datetime import datetime, timezone, timedelta
from services.ratio_service import _safe_div, _cagr
from services.alert_service import should_trigger
from services.signal_service import _compute_signal
from routers.backtest import PRESET_STRATEGIES


def test_safe_div():
    assert _safe_div(10, 2) == 5.0
    assert _safe_div(10, 0) is None
    assert _safe_div(None, 5) is None
    assert _safe_div("abc", 5) is None


def test_cagr():
    # 100 growing to 121 in 2 years is exactly 10%
    result = _cagr(121.0, 100.0, 2)
    assert result is not None
    assert round(result, 4) == 0.1000

    # Negative / zero cases should return None
    assert _cagr(-100, 100, 2) is None
    assert _cagr(100, -100, 2) is None
    assert _cagr(100, 0, 2) is None
    assert _cagr(100, 100, 0) is None


class DummyAlert:
    def __init__(self, alert_type, condition_value=None, created_at=None):
        self.alert_type = alert_type
        self.condition_value = condition_value
        self.created_at = created_at or datetime.now(timezone.utc) - timedelta(hours=1)


class DummyQuote:
    def __init__(self, ltp, is_stale=False, data_source="LIVE"):
        self.ltp = ltp
        self.is_stale = is_stale
        self.data_source = data_source


def test_alert_price_above():
    alert = DummyAlert("PRICE_ABOVE", 2500.0)
    # Stale or mock quote should NOT trigger
    assert not should_trigger(alert, quote=DummyQuote(2600.0, is_stale=True))
    assert not should_trigger(alert, quote=DummyQuote(2600.0, data_source="MOCK"))
    # Live valid quote above threshold triggers
    assert should_trigger(alert, quote=DummyQuote(2550.0, data_source="UPSTOX_WS"))
    # Below threshold does not trigger
    assert not should_trigger(alert, quote=DummyQuote(2450.0, data_source="UPSTOX_WS"))


def test_alert_price_below():
    alert = DummyAlert("PRICE_BELOW", 1500.0)
    assert should_trigger(alert, quote=DummyQuote(1450.0, data_source="UPSTOX_WS"))
    assert not should_trigger(alert, quote=DummyQuote(1550.0, data_source="UPSTOX_WS"))


class DummyIV:
    def __init__(self, iv_blended=3000.0, upside_pct=30.0, margin_of_safety=0.25):
        self.iv_blended = iv_blended
        self.upside_pct = upside_pct
        self.margin_of_safety = margin_of_safety


class DummyML:
    def __init__(self, risk_score=35, fundamental_score=75, growth_outlook_score=70, valuation_confidence="HIGH"):
        self.risk_score = risk_score
        self.fundamental_score = fundamental_score
        self.growth_outlook_score = growth_outlook_score
        self.valuation_confidence = valuation_confidence


class DummyFlag:
    def __init__(self, flag_type, severity="HIGH", is_active=True):
        self.flag_type = flag_type
        self.severity = severity
        self.is_active = is_active


def test_signal_green_condition():
    iv = DummyIV(upside_pct=30.0, margin_of_safety=0.20)
    ml = DummyML(risk_score=35, fundamental_score=70, valuation_confidence="HIGH")
    sig = _compute_signal(iv, ml, ratio=None, risk_flags=[])
    assert sig["signal_color"] == "GREEN"
    assert sig["signal_label"] == "Potentially Undervalued"


def test_signal_insufficient_data():
    sig = _compute_signal(None, None, ratio=None, risk_flags=[])
    assert sig["signal_color"] == "GREY"
    assert sig["signal_label"] == "Insufficient Data"


def test_signal_critical_flag_blocking():
    iv = DummyIV(upside_pct=40.0, margin_of_safety=0.30)
    ml = DummyML(risk_score=30, fundamental_score=80)
    flag = DummyFlag("ACCOUNTING_FRAUD_INVESTIGATION", severity="CRITICAL", is_active=True)
    sig = _compute_signal(iv, ml, ratio=None, risk_flags=[flag])
    # Critical flag blocks GREEN and forces RED or YELLOW
    assert sig["signal_color"] != "GREEN"
    assert "ACCOUNTING_FRAUD_INVESTIGATION" in sig["blocking_flags"]


def test_preset_strategies():
    assert len(PRESET_STRATEGIES) >= 4
    strategy_ids = [s["id"] for s in PRESET_STRATEGIES]
    assert "graham_net_net" in strategy_ids
    assert "quality_growth" in strategy_ids
    assert "dividend_compounders" in strategy_ids
    assert "green_signal" in strategy_ids
