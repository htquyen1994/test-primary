"""
Gap Detection and Linear Interpolation
========================================
Detects missing candles in OHLCV data and fills them with
linearly interpolated values.

Satisfies: Requirements 2.4, 2.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Timeframe string → timedelta mapping
TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "1m":  timedelta(minutes=1),
    "3m":  timedelta(minutes=3),
    "5m":  timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h":  timedelta(hours=1),
    "2h":  timedelta(hours=2),
    "4h":  timedelta(hours=4),
    "1d":  timedelta(days=1),
}


def timeframe_to_delta(timeframe: str) -> timedelta:
    """Convert a timeframe string to a timedelta."""
    if timeframe not in TIMEFRAME_DELTAS:
        raise ValueError(
            f"Unknown timeframe '{timeframe}'. "
            f"Supported: {list(TIMEFRAME_DELTAS.keys())}"
        )
    return TIMEFRAME_DELTAS[timeframe]


def generate_expected_timestamps(
    start: datetime,
    end: datetime,
    timeframe: str,
) -> List[datetime]:
    """
    Generate the complete expected sequence of candle timestamps
    between start and end (inclusive) for the given timeframe.
    """
    delta = timeframe_to_delta(timeframe)
    timestamps = []
    current = start
    while current <= end:
        timestamps.append(current)
        current += delta
    return timestamps


def detect_gaps(
    expected_timestamps: List[datetime],
    received_timestamps: List[datetime],
) -> List[Tuple[datetime, datetime]]:
    """
    Compare expected vs received timestamp sequences and return
    all missing ranges as (gap_start, gap_end) tuples.

    A gap is any expected timestamp not present in received_timestamps.
    Consecutive missing timestamps are merged into a single range.

    Args:
        expected_timestamps: Complete expected sequence (sorted ascending)
        received_timestamps: Actual received sequence (may have gaps)

    Returns:
        List of (gap_start, gap_end) tuples for each contiguous gap.
        Empty list if no gaps detected.

    Satisfies: Requirement 2.4
    """
    received_set = set(received_timestamps)
    missing = [ts for ts in expected_timestamps if ts not in received_set]

    if not missing:
        return []

    # Merge consecutive missing timestamps into ranges
    gaps: List[Tuple[datetime, datetime]] = []
    gap_start = missing[0]
    gap_end = missing[0]

    for ts in missing[1:]:
        # Check if this timestamp is consecutive with the previous
        # (we don't know the delta here, so just track start/end)
        gap_end = ts

    # Simple approach: return individual missing timestamps as (ts, ts) pairs
    # then merge consecutive ones based on the expected sequence
    gaps = []
    gap_start = missing[0]
    prev = missing[0]

    for ts in missing[1:]:
        # Find index of prev and ts in expected to check if consecutive
        try:
            prev_idx = expected_timestamps.index(prev)
            ts_idx = expected_timestamps.index(ts)
            if ts_idx == prev_idx + 1:
                # Consecutive — extend current gap
                prev = ts
            else:
                # Non-consecutive — close current gap, start new one
                gaps.append((gap_start, prev))
                gap_start = ts
                prev = ts
        except ValueError:
            prev = ts

    gaps.append((gap_start, prev))
    return gaps


def fill_gaps(
    ohlcv_df: pd.DataFrame,
    timeframe: str,
    asset: str = "unknown",
) -> pd.DataFrame:
    """
    Fill missing candles in an OHLCV DataFrame using linear interpolation.

    For each gap between two surrounding candles A and B:
    - Generates N interpolated candles between them
    - Each OHLCV field is linearly interpolated between A's and B's values
    - Volume is set to 0 for interpolated candles (no real trades)

    Args:
        ohlcv_df:  DataFrame with columns [open, high, low, close, volume]
                   indexed by datetime (ascending)
        timeframe: Candle timeframe string (e.g. "15m")
        asset:     Asset symbol for logging

    Returns:
        DataFrame with gaps filled, sorted by timestamp ascending.

    Satisfies: Requirement 2.5
    """
    if ohlcv_df.empty:
        return ohlcv_df

    delta = timeframe_to_delta(timeframe)
    df = ohlcv_df.copy().sort_index()

    timestamps = list(df.index)
    if not timestamps:
        return df

    start = timestamps[0]
    end = timestamps[-1]
    expected = generate_expected_timestamps(start, end, timeframe)
    received = timestamps

    gaps = detect_gaps(expected, received)
    if not gaps:
        return df

    interpolated_rows = []

    for gap_start, gap_end in gaps:
        # Find the candle just before the gap (anchor A)
        before_gap = [ts for ts in timestamps if ts < gap_start]
        after_gap = [ts for ts in timestamps if ts > gap_end]

        if not before_gap or not after_gap:
            logger.warning(
                "Cannot interpolate gap [%s → %s] for %s %s: "
                "missing boundary candle",
                gap_start, gap_end, asset, timeframe,
            )
            continue

        ts_a = before_gap[-1]
        ts_b = after_gap[0]
        candle_a = df.loc[ts_a]
        candle_b = df.loc[ts_b]

        # Generate all missing timestamps in this gap
        missing_in_gap = [ts for ts in expected if gap_start <= ts <= gap_end]

        total_steps = (ts_b - ts_a) / delta  # total steps from A to B

        for ts in missing_in_gap:
            step = (ts - ts_a) / delta  # how far from A (0 < step < total_steps)
            frac = step / total_steps   # fraction [0, 1]

            row = {
                "open":   float(candle_a["open"])  + frac * (float(candle_b["open"])  - float(candle_a["open"])),
                "high":   float(candle_a["high"])  + frac * (float(candle_b["high"])  - float(candle_a["high"])),
                "low":    float(candle_a["low"])   + frac * (float(candle_b["low"])   - float(candle_a["low"])),
                "close":  float(candle_a["close"]) + frac * (float(candle_b["close"]) - float(candle_a["close"])),
                "volume": 0.0,  # no real trades in interpolated candle
                "_interpolated": True,
            }
            interpolated_rows.append((ts, row))

        logger.info(
            "Filled %d gap candle(s) [%s → %s] for %s %s",
            len(missing_in_gap), gap_start, gap_end, asset, timeframe,
        )

    if not interpolated_rows:
        return df

    # Build DataFrame from interpolated rows and merge
    interp_df = pd.DataFrame(
        [row for _, row in interpolated_rows],
        index=[ts for ts, _ in interpolated_rows],
    )

    # Add _interpolated column to original if not present
    if "_interpolated" not in df.columns:
        df["_interpolated"] = False

    result = pd.concat([df, interp_df]).sort_index()
    return result
