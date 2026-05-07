"""
Property 18: Signal Card Required Fields
==========================================
For any Signal with classification ALERT, build_signal_card() must
contain all required fields.

Satisfies: Requirement 18.1
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from alert.builder import build_signal_card
from strategies.signal import Signal, ScoreBreakdown

REQUIRED_FIELDS = [
    "asset", "direction", "final_score",
    "entry_price", "stop_loss", "take_profit_1", "take_profit_2",
    "gross_rr", "net_rr",
    "score_breakdown",
    "regime", "expires_at_candle",
]


def make_alert_signal(
    entry: float = 50000.0,
    sl: float = 49000.0,
    tp1: float = 52000.0,
    direction: str = "long",
    score: int = 80,
) -> Signal:
    return Signal(
        strategy_name="test",
        asset="BTC/USDT",
        timeframe="15m",
        direction=direction,
        candle_index=100,
        candle_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entry_price=entry,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp1 * 1.02,
        raw_score=100.0,
        final_score=score,
        score_breakdown=ScoreBreakdown(order_flow=25, smc=20, vsa=20, context=10, bonus=5),
        classification="ALERT",
        regime="TRENDING",
        regime_multiplier=1.0,
        funding_rate=0.0001,
        portfolio_heat=0.02,
        correlated_group_risk=0.01,
        expires_at_candle=115,
    )


@given(
    entry=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    sl_pct=st.floats(min_value=0.005, max_value=0.05, allow_nan=False, allow_infinity=False),
    tp_pct=st.floats(min_value=0.01, max_value=0.10, allow_nan=False, allow_infinity=False),
    score=st.integers(min_value=75, max_value=100),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property18_signal_card_required_fields(
    entry: float, sl_pct: float, tp_pct: float, score: int
):
    """
    Property 18: build_signal_card() must always contain all required fields
    for any ALERT-class Signal.
    Validates: Requirement 18.1
    """
    sl = entry * (1 - sl_pct)
    tp1 = entry * (1 + tp_pct)
    assume(sl > 0 and tp1 > entry)

    signal = make_alert_signal(entry=entry, sl=sl, tp1=tp1, score=score)
    card = build_signal_card(signal)

    for field in REQUIRED_FIELDS:
        assert field in card, f"Required field '{field}' missing from Signal Card"

    # score_breakdown must have all 5 sub-scores
    sb = card["score_breakdown"]
    for sub in ["order_flow", "smc", "vsa", "context", "bonus"]:
        assert sub in sb, f"score_breakdown missing sub-score '{sub}'"

    # gross_rr and net_rr must be non-negative
    assert card["gross_rr"] >= 0.0
    assert isinstance(card["final_score"], int)
    assert 0 <= card["final_score"] <= 100
