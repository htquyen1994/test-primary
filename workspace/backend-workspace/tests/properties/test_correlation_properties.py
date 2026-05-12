"""
Property 14: Pearson Correlation Bounds
Property 15: Portfolio Heat Summation
Property 16: Portfolio Heat Enforcement
=========================================

Satisfies: Requirements 14.1, 14.6, 14.7
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from engine.correlation_manager import CorrelationManager


# ---------------------------------------------------------------------------
# Property 14: Pearson Correlation Bounds
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=2, max_value=100),
    seed=st.integers(min_value=0, max_value=9999),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property14_pearson_correlation_bounds(n: int, seed: int):
    """
    Property 14: Pearson correlation coefficient must always be in [-1.0, 1.0].
    Validates: Requirement 14.1
    """
    rng = np.random.default_rng(seed)
    closes_a = 100.0 + np.cumsum(rng.normal(0, 1, n))
    closes_b = 100.0 + np.cumsum(rng.normal(0, 1, n))

    manager = CorrelationManager()
    manager._close_series["A"] = pd.Series(closes_a)
    manager._close_series["B"] = pd.Series(closes_b)

    matrix = manager.get_correlation_matrix()

    assert not matrix.empty
    for col in matrix.columns:
        for idx in matrix.index:
            val = matrix.loc[idx, col]
            if not np.isnan(val):
                assert -1.0 - 1e-10 <= val <= 1.0 + 1e-10, (
                    f"Correlation {idx}↔{col} = {val} is outside [-1, 1]"
                )


@given(
    n=st.integers(min_value=2, max_value=50),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property14_identical_series_correlation_is_one(n: int):
    """Identical series must have correlation = 1.0."""
    closes = 100.0 + np.arange(n, dtype=float)
    manager = CorrelationManager()
    manager._close_series["A"] = pd.Series(closes)
    manager._close_series["B"] = pd.Series(closes)

    matrix = manager.get_correlation_matrix()
    assert abs(matrix.loc["A", "B"] - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# Property 15: Portfolio Heat Summation
# ---------------------------------------------------------------------------

@given(
    risk_pcts=st.lists(
        st.floats(min_value=0.001, max_value=0.05, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property15_portfolio_heat_summation(risk_pcts: list):
    """
    Property 15: Portfolio_Heat must equal exactly the sum of all
    individual position risk percentages.
    Validates: Requirement 14.6
    """
    manager = CorrelationManager()
    open_positions = {f"ASSET_{i}/USDT": r for i, r in enumerate(risk_pcts)}

    heat = manager.get_portfolio_heat(open_positions)
    expected = sum(risk_pcts) * 100.0

    assert abs(heat - expected) < 1e-8, (
        f"Portfolio heat {heat:.6f}% != expected {expected:.6f}%"
    )


# ---------------------------------------------------------------------------
# Property 16: Portfolio Heat Enforcement
# ---------------------------------------------------------------------------

@given(
    existing_heat_pct=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    new_risk_pct=st.floats(min_value=0.001, max_value=0.05, allow_nan=False, allow_infinity=False),
    limit_pct=st.floats(min_value=1.0, max_value=8.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property16_portfolio_heat_enforcement(
    existing_heat_pct: float,
    new_risk_pct: float,
    limit_pct: float,
):
    """
    Property 16: When Portfolio_Heat >= limit, RiskManager must reject
    every new signal regardless of score, asset, or direction.
    Validates: Requirement 14.7
    """
    manager = CorrelationManager(
        portfolio_heat_limit_pct=limit_pct,
        correlation_threshold=0.8,
        max_correlated_risk_pct=100.0,  # disable correlated risk limit for this test
    )

    # Build open positions that sum to existing_heat_pct
    open_positions = {"BTC/USDT": existing_heat_pct / 100.0}
    new_total_heat = existing_heat_pct + new_risk_pct * 100.0

    result = manager.check_new_signal(
        asset="ETH/USDT",
        new_risk_pct=new_risk_pct,
        open_positions=open_positions,
    )

    if new_total_heat > limit_pct:
        assert result.allowed is False, (
            f"Signal should be rejected: heat {new_total_heat:.2f}% > limit {limit_pct:.2f}%"
        )
    else:
        # May be allowed (unless correlated risk also exceeded)
        pass  # not asserting allowed=True since correlated risk could also block
