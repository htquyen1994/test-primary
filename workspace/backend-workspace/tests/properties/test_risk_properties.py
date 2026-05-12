"""
Property 7: Risk Cap Invariant
================================
For any account equity, risk percentage, entry price, and stop-loss distance,
the maximum possible loss from the position size returned by RiskManager
must never exceed equity × max_risk_pct.

Satisfies: Requirements 7.1, 7.3
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from risk.manager import RiskManager


@given(
    equity=st.floats(min_value=100.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    risk_pct=st.floats(min_value=0.001, max_value=0.05, allow_nan=False, allow_infinity=False),
    entry=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    sl_distance_pct=st.floats(min_value=0.001, max_value=0.10, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property7_risk_cap_invariant_risk_pct_mode(
    equity: float,
    risk_pct: float,
    entry: float,
    sl_distance_pct: float,
):
    """
    Property 7 (risk_pct mode): max loss must never exceed equity × max_risk_pct.
    Validates: Requirements 7.1, 7.3
    """
    stop_loss = entry * (1 - sl_distance_pct)
    atr = entry * sl_distance_pct  # non-zero ATR

    manager = RiskManager(
        mode="risk_pct",
        risk_pct=risk_pct,
        max_risk_pct=risk_pct,
        leverage=1,
        market_type="spot",
    )

    result = manager.compute_position_size(
        asset="BTC/USDT",
        entry_price=entry,
        stop_loss=stop_loss,
        account_equity=equity,
        atr_value=atr,
    )

    if result.allowed:
        sl_dist = abs(entry - stop_loss)
        max_loss = result.position_size_usd * (sl_dist / entry)
        max_allowed_loss = equity * risk_pct

        assert max_loss <= max_allowed_loss * 1.01, (  # 1% tolerance for fee inclusion
            f"Max loss {max_loss:.4f} exceeds equity × risk_pct {max_allowed_loss:.4f}"
        )


@given(
    equity=st.floats(min_value=100.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    fixed_usd=st.floats(min_value=10.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    entry=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    sl_distance_pct=st.floats(min_value=0.001, max_value=0.10, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property7_risk_cap_invariant_fixed_usd_mode(
    equity: float,
    fixed_usd: float,
    entry: float,
    sl_distance_pct: float,
):
    """
    Property 7 (fixed_usd mode): position size = fixed_usd (capped by max_risk_pct).
    """
    stop_loss = entry * (1 - sl_distance_pct)
    atr = entry * sl_distance_pct

    manager = RiskManager(
        mode="fixed_usd",
        fixed_usd=fixed_usd,
        max_risk_pct=0.05,  # 5% cap
        leverage=1,
        market_type="spot",
    )

    result = manager.compute_position_size(
        asset="BTC/USDT",
        entry_price=entry,
        stop_loss=stop_loss,
        account_equity=equity,
        atr_value=atr,
    )

    if result.allowed:
        sl_dist = abs(entry - stop_loss)
        max_loss = result.position_size_usd * (sl_dist / entry)
        max_allowed_loss = equity * 0.05

        assert max_loss <= max_allowed_loss * 1.01, (
            f"Max loss {max_loss:.4f} exceeds cap {max_allowed_loss:.4f}"
        )
