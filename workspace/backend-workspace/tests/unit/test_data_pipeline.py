"""
Unit tests for the Data Pipeline modules.
Tests gap detection, interpolation, retry logic, and funding rate fallback.

Satisfies: Requirements 2.4, 2.5, 2.6, 3.4
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pandas as pd
import pytest

from data.gap_filler import detect_gaps, fill_gaps, generate_expected_timestamps
from data.ccxt_client import retry_with_backoff, DataFetchError


BASE_TIME = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
DELTA_15M = timedelta(minutes=15)


def make_timestamps(n: int) -> list:
    return [BASE_TIME + i * DELTA_15M for i in range(n)]


# ---------------------------------------------------------------------------
# Gap detection tests
# ---------------------------------------------------------------------------

class TestGapDetection:

    def test_no_gaps(self):
        ts = make_timestamps(5)
        assert detect_gaps(ts, ts) == []

    def test_single_gap(self):
        expected = make_timestamps(5)
        received = [expected[0], expected[1], expected[3], expected[4]]
        gaps = detect_gaps(expected, received)
        assert len(gaps) == 1
        assert gaps[0] == (expected[2], expected[2])

    def test_three_non_contiguous_gaps(self):
        expected = make_timestamps(10)
        received = [ts for i, ts in enumerate(expected) if i not in {2, 5, 8}]
        gaps = detect_gaps(expected, received)
        all_gap_ts = {ts for start, end in gaps for ts in [start, end]}
        assert expected[2] in all_gap_ts
        assert expected[5] in all_gap_ts
        assert expected[8] in all_gap_ts

    def test_empty_received_returns_one_gap(self):
        expected = make_timestamps(5)
        gaps = detect_gaps(expected, [])
        assert len(gaps) == 1


# ---------------------------------------------------------------------------
# Linear interpolation tests
# ---------------------------------------------------------------------------

class TestLinearInterpolation:

    def test_midpoint_interpolation(self):
        ts_a = BASE_TIME
        ts_b = BASE_TIME + 2 * DELTA_15M
        df = pd.DataFrame(
            {"open": [100, 200], "high": [101, 201], "low": [99, 199],
             "close": [100.0, 200.0], "volume": [1000, 1000]},
            index=[ts_a, ts_b],
        )
        result = fill_gaps(df, "15m")
        ts_gap = BASE_TIME + DELTA_15M
        assert ts_gap in result.index
        assert abs(result.loc[ts_gap, "close"] - 150.0) < 1e-10

    def test_all_ohlcv_fields_interpolated(self):
        ts_a = BASE_TIME
        ts_b = BASE_TIME + 2 * DELTA_15M
        df = pd.DataFrame(
            {"open": [10.0, 20.0], "high": [12.0, 22.0],
             "low": [8.0, 18.0], "close": [11.0, 21.0], "volume": [500, 600]},
            index=[ts_a, ts_b],
        )
        result = fill_gaps(df, "15m")
        ts_gap = BASE_TIME + DELTA_15M
        assert abs(result.loc[ts_gap, "open"] - 15.0) < 1e-10
        assert abs(result.loc[ts_gap, "high"] - 17.0) < 1e-10
        assert abs(result.loc[ts_gap, "low"] - 13.0) < 1e-10
        assert abs(result.loc[ts_gap, "close"] - 16.0) < 1e-10
        assert result.loc[ts_gap, "volume"] == 0.0  # no real trades

    def test_result_sorted_ascending(self):
        ts = make_timestamps(5)
        received = [ts[0], ts[1], ts[3], ts[4]]
        df = pd.DataFrame(
            {"open": [100]*4, "high": [101]*4, "low": [99]*4,
             "close": [100.0]*4, "volume": [1000]*4},
            index=received,
        )
        result = fill_gaps(df, "15m")
        assert list(result.index) == sorted(result.index)


# ---------------------------------------------------------------------------
# Retry logic tests
# ---------------------------------------------------------------------------

class TestRetryWithBackoff:

    def test_succeeds_on_first_attempt(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.001)
        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = fn()
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_failure_then_succeeds(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.001)
        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary error")
            return "ok"

        result = fn()
        assert result == "ok"
        assert call_count == 3  # failed twice, succeeded on third

    def test_raises_data_fetch_error_after_all_retries(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.001)
        def fn():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always fails")

        with pytest.raises(DataFetchError) as exc_info:
            fn()

        assert call_count == 3
        assert exc_info.value.attempts == 3
        assert "always fails" in str(exc_info.value.last_error)

    def test_async_retry_succeeds_on_third_attempt(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.001)
        async def async_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("temporary")
            return "async_ok"

        result = asyncio.get_event_loop().run_until_complete(async_fn())
        assert result == "async_ok"
        assert call_count == 3

    def test_async_raises_after_all_retries(self):
        @retry_with_backoff(max_retries=2, base_delay=0.001)
        async def async_fn():
            raise ValueError("always fails")

        with pytest.raises(DataFetchError):
            asyncio.get_event_loop().run_until_complete(async_fn())


# ---------------------------------------------------------------------------
# Funding rate fallback test
# ---------------------------------------------------------------------------

class TestFundingRateFallback:

    @pytest.mark.asyncio
    async def test_fallback_to_zero_when_unavailable(self):
        """
        When funding rate API returns empty/None, system uses 0.0.
        Satisfies: Requirement 3.4
        """
        from data.funding import read_funding_rate

        # Mock Redis returning None (key not set)
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        rate = await read_funding_rate(mock_redis, "BTC/USDT")
        assert rate == 0.0

    @pytest.mark.asyncio
    async def test_reads_rate_from_redis(self):
        import json
        from data.funding import read_funding_rate

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"rate": 0.0003, "timestamp": "2024-01-01T00:00:00+00:00"})
        )

        rate = await read_funding_rate(mock_redis, "BTC/USDT")
        assert abs(rate - 0.0003) < 1e-10
