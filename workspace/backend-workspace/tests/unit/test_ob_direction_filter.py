"""
Unit tests for OB direction filter in compute_smc_score.

Satisfies: TASK-08 — Only OBs aligned with signal_direction contribute score.
  - Long signal  → bullish OB retest scores, bearish OB retest does NOT
  - Short signal → bearish OB retest scores, bullish OB retest does NOT
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.smc import compute_smc_score


# ---------------------------------------------------------------------------
# Helpers — craft OHLCV that guarantees a specific OB retest scenario
# ---------------------------------------------------------------------------

def _base_candles(n: int = 22, price: float = 100.0) -> list:
    """Flat candles to give a stable ATR baseline (~1.0)."""
    return [
        {"open": price, "high": price + 0.5, "low": price - 0.5,
         "close": price, "volume": 500.0}
        for _ in range(n)
    ]


def bullish_ob_retested_ohlcv() -> pd.DataFrame:
    """
    Structure:
      22 flat candles  → stable ATR ≈ 1.0
      OB candle        → bearish, zone [97, 102]  (bullish OB type)
      Impulse candle   → large bullish (body=17 >> 1.5×ATR), drives price up
      Retest candle    → price=100.0, inside OB zone  →  ob_retested expected
    """
    rows = _base_candles(22)
    rows.append({"open": 101.0, "high": 102.0, "low": 97.0, "close": 98.0, "volume": 800.0})  # bearish OB candle
    rows.append({"open": 98.0,  "high": 116.0, "low": 97.5, "close": 115.0, "volume": 5000.0})  # bullish impulse
    rows.append({"open": 101.0, "high": 101.5, "low": 99.5, "close": 100.0, "volume": 600.0})   # retest
    return pd.DataFrame(rows)


def bearish_ob_retested_ohlcv() -> pd.DataFrame:
    """
    Structure:
      22 flat candles  → stable ATR ≈ 1.0
      OB candle        → bullish, zone [96, 104]  (bearish OB type)
      Impulse candle   → large bearish (body=17 >> 1.5×ATR), drives price down
      Retest candle    → price=100.0, inside OB zone  →  ob_retested expected
    """
    rows = _base_candles(22)
    rows.append({"open": 97.0,  "high": 104.0, "low": 96.0, "close": 103.0, "volume": 800.0})  # bullish OB candle
    rows.append({"open": 103.0, "high": 103.5, "low": 85.0, "close": 86.0,  "volume": 5000.0})  # bearish impulse
    rows.append({"open": 99.0,  "high": 101.0, "low": 98.0, "close": 100.0, "volume": 600.0})   # retest
    return pd.DataFrame(rows)


def flat_ohlcv(n: int = 30, price: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({
        "open":   [price] * n, "high": [price + 0.5] * n,
        "low":    [price - 0.5] * n, "close": [price] * n,
        "volume": [1000.0] * n,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOBDirectionFilter:

    def test_bullish_ob_retested_scores_for_long(self):
        """Bullish OB retest + long signal → ob_retested=True, +10 pts from OB."""
        ohlcv = bullish_ob_retested_ohlcv()
        result = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="long")

        assert result.ob_retested is True
        assert result.order_block is not None
        assert result.order_block.type == "bullish"
        assert result.score >= 10.0

    def test_bullish_ob_retest_suppressed_for_short(self):
        """
        Bullish OB is demand/support — irrelevant for short signals.
        When signal_direction='short', a bullish OB retest must NOT add score.
        """
        ohlcv = bullish_ob_retested_ohlcv()
        result = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="short")

        assert result.ob_retested is False, (
            "Bullish OB should not be scored for a short signal"
        )

    def test_bearish_ob_retested_scores_for_short(self):
        """Bearish OB retest + short signal → ob_retested=True, +10 pts from OB."""
        ohlcv = bearish_ob_retested_ohlcv()
        result = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="short")

        assert result.ob_retested is True
        assert result.order_block is not None
        assert result.order_block.type == "bearish"
        assert result.score >= 10.0

    def test_bearish_ob_retest_suppressed_for_long(self):
        """
        Bearish OB is supply/resistance — irrelevant for long signals.
        When signal_direction='long', a bearish OB retest must NOT add score.
        """
        ohlcv = bearish_ob_retested_ohlcv()
        result = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="long")

        assert result.ob_retested is False, (
            "Bearish OB should not be scored for a long signal"
        )

    def test_default_direction_is_long(self):
        """Default signal_direction='long' → same behaviour as explicit 'long'."""
        ohlcv = bullish_ob_retested_ohlcv()
        with_default = compute_smc_score(ohlcv, flat_ohlcv())
        with_explicit = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="long")

        assert with_default.ob_retested == with_explicit.ob_retested
        assert with_default.score == with_explicit.score

    def test_ob_score_delta_is_ten_points(self):
        """Suppressing OB retest removes exactly 10 pts from the score."""
        ohlcv = bullish_ob_retested_ohlcv()
        score_long  = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="long").score
        score_short = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="short").score

        assert score_long - score_short == pytest.approx(10.0), (
            f"Expected 10 pt difference, got {score_long - score_short}"
        )

    def test_no_ob_scenario_unaffected_by_direction(self):
        """When no OB exists, ob_retested=False regardless of signal_direction."""
        ohlcv = flat_ohlcv(30)
        long_result  = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="long")
        short_result = compute_smc_score(ohlcv, flat_ohlcv(), signal_direction="short")

        assert long_result.ob_retested is False
        assert short_result.ob_retested is False
