"""
Property 3: Gap Detection Completeness
Property 4: Linear Interpolation Correctness
=============================================

Property 3: For any expected timestamp sequence and received sequence
with randomly removed timestamps, detect_gaps() must identify every
missing timestamp — no gap may be silently skipped.

Property 4: For any two OHLCV candles A and B, each interpolated
OHLCV field value must lie exactly on the linear path between A and B.

Satisfies: Requirements 2.4, 2.5
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pandas as pd
import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from data.gap_filler import detect_gaps, fill_gaps, generate_expected_timestamps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_TIME = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
DELTA_15M = timedelta(minutes=15)


def make_timestamps(n: int, delta: timedelta = DELTA_15M) -> List[datetime]:
    return [BASE_TIME + i * delta for i in range(n)]


def make_ohlcv_df(timestamps: List[datetime], base_price: float = 100.0) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame for the given timestamps."""
    n = len(timestamps)
    prices = [base_price + i * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "open":   [p - 0.1 for p in prices],
            "high":   [p + 0.5 for p in prices],
            "low":    [p - 0.5 for p in prices],
            "close":  prices,
            "volume": [1000.0] * n,
        },
        index=timestamps,
    )


# ---------------------------------------------------------------------------
# Unit tests — specific scenarios
# ---------------------------------------------------------------------------

class TestGapDetectionUnit:

    def test_no_gaps_returns_empty(self):
        timestamps = make_timestamps(10)
        gaps = detect_gaps(timestamps, timestamps)
        assert gaps == []

    def test_single_missing_timestamp(self):
        expected = make_timestamps(5)
        received = [expected[0], expected[1], expected[3], expected[4]]  # missing [2]
        gaps = detect_gaps(expected, received)
        assert len(gaps) == 1
        assert gaps[0] == (expected[2], expected[2])

    def test_three_non_contiguous_gaps(self):
        expected = make_timestamps(10)
        # Remove indices 2, 5, 8
        received = [ts for i, ts in enumerate(expected) if i not in {2, 5, 8}]
        gaps = detect_gaps(expected, received)
        missing_timestamps = [ts for start, end in gaps for ts in [start, end]]
        assert expected[2] in missing_timestamps
        assert expected[5] in missing_timestamps
        assert expected[8] in missing_timestamps

    def test_contiguous_gap_merged(self):
        expected = make_timestamps(10)
        # Remove indices 3, 4, 5 (contiguous)
        received = [ts for i, ts in enumerate(expected) if i not in {3, 4, 5}]
        gaps = detect_gaps(expected, received)
        # Should be one gap covering [3..5]
        assert len(gaps) == 1
        assert gaps[0][0] == expected[3]
        assert gaps[0][1] == expected[5]

    def test_all_missing_returns_one_gap(self):
        expected = make_timestamps(5)
        gaps = detect_gaps(expected, [])
        assert len(gaps) == 1
        assert gaps[0][0] == expected[0]
        assert gaps[0][1] == expected[-1]


class TestLinearInterpolationUnit:

    def test_no_gaps_returns_unchanged(self):
        timestamps = make_timestamps(5)
        df = make_ohlcv_df(timestamps)
        result = fill_gaps(df, "15m")
        assert len(result) == len(df)

    def test_interpolated_close_between_endpoints(self):
        # A: close=100, B: close=200, one gap in between
        ts_a = BASE_TIME
        ts_b = BASE_TIME + 2 * DELTA_15M
        ts_gap = BASE_TIME + DELTA_15M

        df = pd.DataFrame(
            {"open": [99, 199], "high": [101, 201], "low": [98, 198],
             "close": [100.0, 200.0], "volume": [1000, 1000]},
            index=[ts_a, ts_b],
        )
        result = fill_gaps(df, "15m")
        assert ts_gap in result.index
        # Interpolated close should be exactly 150.0 (midpoint)
        assert abs(result.loc[ts_gap, "close"] - 150.0) < 1e-10

    def test_interpolated_volume_is_zero(self):
        ts_a = BASE_TIME
        ts_b = BASE_TIME + 2 * DELTA_15M
        df = pd.DataFrame(
            {"open": [100, 200], "high": [101, 201], "low": [99, 199],
             "close": [100.0, 200.0], "volume": [5000.0, 6000.0]},
            index=[ts_a, ts_b],
        )
        result = fill_gaps(df, "15m")
        ts_gap = BASE_TIME + DELTA_15M
        assert result.loc[ts_gap, "volume"] == 0.0

    def test_result_sorted_ascending(self):
        timestamps = make_timestamps(5)
        # Remove middle timestamp
        received = [timestamps[0], timestamps[1], timestamps[3], timestamps[4]]
        df = make_ohlcv_df(received)
        result = fill_gaps(df, "15m")
        assert list(result.index) == sorted(result.index)


# ---------------------------------------------------------------------------
# Property 3: Gap Detection Completeness
# ---------------------------------------------------------------------------

@given(
    n_total=st.integers(min_value=3, max_value=50),
    remove_indices=st.lists(
        st.integers(min_value=1, max_value=48),
        min_size=1,
        max_size=10,
        unique=True,
    ),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property3_gap_detection_completeness(n_total: int, remove_indices: list):
    """
    Property 3: For any expected sequence with randomly removed timestamps,
    detect_gaps() must identify every missing timestamp.
    No gap may be silently skipped.
    """
    expected = make_timestamps(n_total)
    # Filter remove_indices to valid range
    to_remove = {i for i in remove_indices if i < n_total}
    assume(len(to_remove) > 0)

    received = [ts for i, ts in enumerate(expected) if i not in to_remove]
    gaps = detect_gaps(expected, received)

    # Collect all timestamps covered by the detected gaps
    detected_missing = set()
    for gap_start, gap_end in gaps:
        for ts in expected:
            if gap_start <= ts <= gap_end:
                detected_missing.add(ts)

    # Every removed timestamp must be in a detected gap
    for i in to_remove:
        assert expected[i] in detected_missing, (
            f"Gap detection missed timestamp at index {i}: {expected[i]}"
        )


# ---------------------------------------------------------------------------
# Property 4: Linear Interpolation Correctness
# ---------------------------------------------------------------------------

@given(
    close_a=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    close_b=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    n_gaps=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property4_linear_interpolation_correctness(
    close_a: float, close_b: float, n_gaps: int
):
    """
    Property 4: For any two candles A and B with n_gaps candles between them,
    each interpolated close value must lie exactly on the linear path from A to B.
    """
    # Build DataFrame with A and B, n_gaps missing in between
    ts_a = BASE_TIME
    ts_b = BASE_TIME + (n_gaps + 1) * DELTA_15M

    df = pd.DataFrame(
        {
            "open":   [close_a - 0.1, close_b - 0.1],
            "high":   [close_a + 0.5, close_b + 0.5],
            "low":    [close_a - 0.5, close_b - 0.5],
            "close":  [close_a, close_b],
            "volume": [1000.0, 1000.0],
        },
        index=[ts_a, ts_b],
    )

    result = fill_gaps(df, "15m")

    # Check each interpolated candle
    for step in range(1, n_gaps + 1):
        ts = BASE_TIME + step * DELTA_15M
        assert ts in result.index, f"Missing interpolated candle at step {step}"

        frac = step / (n_gaps + 1)
        expected_close = close_a + frac * (close_b - close_a)
        actual_close = result.loc[ts, "close"]

        assert abs(actual_close - expected_close) < 1e-8, (
            f"Interpolation error at step {step}/{n_gaps+1}: "
            f"expected {expected_close:.6f}, got {actual_close:.6f}"
        )
