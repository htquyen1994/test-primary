"""
Property 17: Signal Log Completeness
======================================
For any batch of N signals, exactly N Signal_Log entries must be written.

Satisfies: Requirement 17.1
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import List
from unittest.mock import MagicMock, patch, call

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from strategies.signal import Signal, ScoreBreakdown


def make_signal(classification: str = "ALERT", score: int = 80) -> Signal:
    return Signal(
        strategy_name="test", asset="BTC/USDT", timeframe="15m",
        direction="long", candle_index=100,
        candle_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entry_price=50000.0, stop_loss=49000.0,
        take_profit_1=52000.0, take_profit_2=54000.0,
        raw_score=100.0, final_score=score,
        score_breakdown=ScoreBreakdown(order_flow=25, smc=20, vsa=20, context=10, bonus=5),
        classification=classification, regime="TRENDING",
        regime_multiplier=1.0, funding_rate=0.0001,
        portfolio_heat=0.02, correlated_group_risk=0.01,
        expires_at_candle=115,
    )


@given(
    n=st.integers(min_value=1, max_value=20),
    classifications=st.lists(
        st.sampled_from(["ALERT", "WATCH", "IGNORE"]),
        min_size=1, max_size=20,
    )
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_property17_signal_log_completeness(n: int, classifications: list):
    """
    Property 17: For any batch of N signals, exactly N Signal_Log entries
    must be written, regardless of classification.
    Validates: Requirement 17.1
    """
    assume(len(classifications) >= n)
    signals = [make_signal(classifications[i]) for i in range(n)]

    # Mock the DB session
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()

    # Patch SignalLog model to avoid DB dependency
    with patch("db.models.SignalLog") as MockSignalLog:
        MockSignalLog.return_value = MagicMock()
        from api.signal_log_writer import write_signal_log
        for signal in signals:
            write_signal_log(signal, mock_db)

    # Exactly N rows must have been added
    assert mock_db.add.call_count == n, (
        f"Expected {n} Signal_Log entries, got {mock_db.add.call_count}"
    )
    assert mock_db.commit.call_count == n
