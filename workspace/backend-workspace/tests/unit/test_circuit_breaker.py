"""
Unit tests for CircuitBreaker Trigger 4 — 7-day equity peak detection.

Satisfies: TASK-03 — Fix _get_7day_equity_peak stub (always returned 0.0)
Requirements: 22 (Phase 9 Circuit Breaker)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from risk.circuit_breaker import CircuitBreaker, DRAWDOWN_FROM_PEAK_PCT, DRAWDOWN_PEAK_WINDOW_DAYS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cb(redis_mock=None, db_rows=None, redis_cache=None):
    """
    Build a CircuitBreaker with mocked Redis and DB.

    Args:
        redis_mock:   pre-built Redis mock (created if None)
        db_rows:      list of net_pnl values for trade_journal rows (in chronological order)
        redis_cache:  bytes value to return for r.get(_CACHE_KEY), or None
    """
    cb = CircuitBreaker()

    # Redis mock
    r = redis_mock or MagicMock()
    _CACHE_KEY = "circuit_breaker:7day_peak"
    if redis_cache is not None:
        r.get = MagicMock(side_effect=lambda key: redis_cache if key == _CACHE_KEY else None)
    else:
        r.get = MagicMock(return_value=None)
    r.set = MagicMock()
    cb._get_redis = MagicMock(return_value=r)

    # DB mock
    db = MagicMock()
    if db_rows is not None:
        rows = [MagicMock(net_pnl=pnl) for pnl in db_rows]
        db.execute.return_value.fetchall.return_value = rows
    else:
        db.execute.return_value.fetchall.return_value = []
    db.close = MagicMock()
    cb._get_db = MagicMock(return_value=db)

    return cb, r


# ---------------------------------------------------------------------------
# Tests: _get_7day_equity_peak
# ---------------------------------------------------------------------------

class TestGet7DayEquityPeak:

    def test_returns_current_equity_when_no_trades(self):
        """No trades in window → peak = current_equity."""
        cb, _ = _make_cb(db_rows=[])
        assert cb._get_7day_equity_peak(10000.0) == 10000.0

    def test_peak_above_current_after_losses(self):
        """After a string of losses, peak > current_equity."""
        # Trades: -200, -300 → equity went from 10500 → 10000
        cb, _ = _make_cb(db_rows=[-200.0, -300.0])
        peak = cb._get_7day_equity_peak(10000.0)
        # equity before -200 trade = 10000 - (-200 + -300) = 10500
        assert peak == pytest.approx(10500.0)

    def test_peak_equals_current_after_gains(self):
        """After a string of gains, peak = current_equity (latest point)."""
        cb, _ = _make_cb(db_rows=[100.0, 200.0, 150.0])
        peak = cb._get_7day_equity_peak(10000.0)
        # All gains → current_equity is the highest point
        assert peak == pytest.approx(10000.0)

    def test_peak_at_midpoint_mixed_trades(self):
        """Mixed gains then losses → peak is somewhere in the middle."""
        # net_pnl: [+500, +300, -800, -200]
        # suffix_sums: [−200, −700, −1000, −200]
        # equities before each trade:
        #   before T1: 10000 − (500+300−800−200) = 10000 − (−200) = 10200
        #   before T2: 10000 − (300−800−200)     = 10000 − (−700) = 10700
        #   before T3: 10000 − (−800−200)         = 10000 − (−1000) = 11000  ← peak
        #   before T4: 10000 − (−200)             = 10000 + 200 = 10200
        #   after T4 (current):                  10000
        cb, _ = _make_cb(db_rows=[500.0, 300.0, -800.0, -200.0])
        peak = cb._get_7day_equity_peak(10000.0)
        assert peak == pytest.approx(11000.0)

    def test_single_winning_trade(self):
        """Single gain → peak is before the trade."""
        # net_pnl: [+500]
        # equity before: 10000 − 500 = 9500
        # current:                     10000 ← peak
        cb, _ = _make_cb(db_rows=[500.0])
        peak = cb._get_7day_equity_peak(10000.0)
        assert peak == pytest.approx(10000.0)

    def test_single_losing_trade(self):
        """Single loss → peak was before the trade."""
        # net_pnl: [−500]
        # equity before: 10000 − (−500) = 10500  ← peak
        # current:                        10000
        cb, _ = _make_cb(db_rows=[-500.0])
        peak = cb._get_7day_equity_peak(10000.0)
        assert peak == pytest.approx(10500.0)

    def test_redis_cache_hit_skips_db(self):
        """When Redis has a cached value, DB is not queried."""
        cb, r = _make_cb(redis_cache=b"12345.67")
        peak = cb._get_7day_equity_peak(10000.0)
        assert peak == pytest.approx(12345.67)
        cb._get_db.assert_not_called()

    def test_result_cached_in_redis_after_db_query(self):
        """After DB query, result is written to Redis with 1-hour TTL."""
        cb, r = _make_cb(db_rows=[-100.0])
        cb._get_7day_equity_peak(10000.0)
        r.set.assert_called_once()
        call_args = r.set.call_args
        assert call_args[0][0] == "circuit_breaker:7day_peak"
        assert call_args[1]["ex"] == 3600

    def test_returns_zero_on_db_error(self):
        """DB failure → return 0.0, not raise."""
        cb = CircuitBreaker()
        r = MagicMock()
        r.get.return_value = None
        cb._get_redis = MagicMock(return_value=r)
        db = MagicMock()
        db.execute.side_effect = Exception("DB unavailable")
        cb._get_db = MagicMock(return_value=db)

        result = cb._get_7day_equity_peak(10000.0)
        assert result == 0.0

    def test_peak_always_gte_zero(self):
        """Peak is never negative."""
        cb, _ = _make_cb(db_rows=[-5000.0, -3000.0])
        peak = cb._get_7day_equity_peak(1000.0)
        assert peak >= 0.0


# ---------------------------------------------------------------------------
# Tests: check_drawdown (integration of peak detection into Trigger 4)
# ---------------------------------------------------------------------------

class TestCheckDrawdown:

    def _make_cb_with_peak(self, peak_value: float, current_equity: float):
        """Build CB where _get_7day_equity_peak returns a specific value."""
        cb = CircuitBreaker()
        r = MagicMock()
        r.get.return_value = None
        r.set = MagicMock()
        r.publish = MagicMock()
        cb._get_redis = MagicMock(return_value=r)

        # Mock _get_7day_equity_peak to return controlled value
        cb._get_7day_equity_peak = MagicMock(return_value=peak_value)

        # Mock is_locked to return False
        cb.is_locked = MagicMock(return_value=False)

        # Mock _activate to avoid DB
        cb._activate = MagicMock(return_value=MagicMock(is_locked=True))

        return cb

    def test_trigger4_fires_when_drawdown_exceeds_threshold(self):
        """10% drawdown from $11000 peak with current $9000 (18%) → trigger fires."""
        peak = 11000.0
        current = 9000.0  # drawdown = (11000-9000)/11000 = 18% > 10%
        cb = self._make_cb_with_peak(peak, current)
        result = cb.check_drawdown(current, regime="CHOPPY")
        cb._activate.assert_called_once()
        call_kwargs = cb._activate.call_args[1]
        assert call_kwargs["trigger_type"] == "DRAWDOWN_FROM_PEAK"
        assert call_kwargs["requires_review"] is True

    def test_trigger4_does_not_fire_below_threshold(self):
        """5% drawdown < 10% threshold → no trigger."""
        peak = 10500.0
        current = 10000.0  # drawdown = 500/10500 = 4.76% < 10%
        cb = self._make_cb_with_peak(peak, current)
        result = cb.check_drawdown(current, regime="TRENDING")
        cb._activate.assert_not_called()
        assert result is None

    def test_trigger4_skipped_when_peak_is_zero(self):
        """Peak = 0 (no data) → no trigger (avoids false positives)."""
        cb = self._make_cb_with_peak(0.0, 10000.0)
        result = cb.check_drawdown(10000.0, regime="TRENDING")
        cb._activate.assert_not_called()
        assert result is None

    def test_trigger4_skipped_when_already_locked(self):
        """Already locked → check_drawdown returns None immediately."""
        cb = CircuitBreaker()
        cb.is_locked = MagicMock(return_value=True)
        cb._get_7day_equity_peak = MagicMock()
        result = cb.check_drawdown(10000.0, regime="TRENDING")
        cb._get_7day_equity_peak.assert_not_called()
        assert result is None

    def test_trigger4_exactly_at_threshold_fires(self):
        """Exactly 10% drawdown → trigger fires (boundary: > not >=)."""
        # drawdown = 10.01% → fires
        peak = 10000.0
        current = 8999.0  # (10000 - 8999) / 10000 = 10.01%
        cb = self._make_cb_with_peak(peak, current)
        cb.check_drawdown(current, regime="CHOPPY")
        cb._activate.assert_called_once()

    def test_trigger4_just_below_threshold_no_fire(self):
        """9.99% drawdown → does not fire."""
        peak = 10000.0
        current = 9001.0  # (10000 - 9001) / 10000 = 9.99%
        cb = self._make_cb_with_peak(peak, current)
        result = cb.check_drawdown(current, regime="TRENDING")
        cb._activate.assert_not_called()
        assert result is None
