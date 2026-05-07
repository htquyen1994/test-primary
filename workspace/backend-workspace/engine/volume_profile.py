"""
Volume Profile Calculator
==========================
Computes Point of Control (POC), Value Area High (VAH), Value Area Low (VAL)
from OHLCV data over a configurable window.

POC  = price level with the highest traded volume
VAH  = upper boundary of the 70% value area
VAL  = lower boundary of the 70% value area

Used by VSA module for confluence scoring.
Stored in Redis key poc:{symbol}, updated every 15m.

Satisfies: Requirement 6.2 (VSA+VolProfile component)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

VALUE_AREA_PCT = 0.70   # 70% of total volume defines the value area
DEFAULT_BINS = 50       # number of price bins for volume distribution


@dataclass
class VolumeProfile:
    """Point of Control and Value Area boundaries."""
    poc: float      # price level with highest volume
    vah: float      # Value Area High (upper 70% boundary)
    val: float      # Value Area Low (lower 70% boundary)
    total_volume: float

    def is_price_at_poc(self, price: float, tolerance_pct: float = 0.003) -> bool:
        """Returns True if price is within tolerance_pct of POC."""
        if self.poc == 0:
            return False
        return abs(price - self.poc) / self.poc <= tolerance_pct

    def is_price_at_value_area_edge(self, price: float, tolerance_pct: float = 0.003) -> bool:
        """Returns True if price is near VAH or VAL."""
        if self.vah == 0 or self.val == 0:
            return False
        at_vah = abs(price - self.vah) / self.vah <= tolerance_pct
        at_val = abs(price - self.val) / self.val <= tolerance_pct
        return at_vah or at_val


def compute_volume_profile(
    ohlcv: pd.DataFrame,
    bins: int = DEFAULT_BINS,
    value_area_pct: float = VALUE_AREA_PCT,
) -> VolumeProfile:
    """
    Compute Volume Profile from OHLCV data.

    Algorithm:
    1. Distribute each candle's volume across price bins proportionally
       (volume allocated to bins that overlap with the candle's high-low range)
    2. POC = bin with highest total volume
    3. Value Area = expand from POC outward until 70% of total volume is captured

    Args:
        ohlcv:          DataFrame with [open, high, low, close, volume]
        bins:           Number of price bins (default 50)
        value_area_pct: Fraction of total volume for value area (default 0.70)

    Returns:
        VolumeProfile with poc, vah, val

    Satisfies: Requirement 6.2 (Volume Profile component)
    """
    if ohlcv.empty or len(ohlcv) < 2:
        return VolumeProfile(poc=0.0, vah=0.0, val=0.0, total_volume=0.0)

    price_min = float(ohlcv["low"].min())
    price_max = float(ohlcv["high"].max())

    if price_min >= price_max:
        mid = (price_min + price_max) / 2
        return VolumeProfile(poc=mid, vah=mid, val=mid,
                             total_volume=float(ohlcv["volume"].sum()))

    # Create price bins
    bin_edges = np.linspace(price_min, price_max, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_volume = np.zeros(bins)

    # Distribute each candle's volume across overlapping bins
    for _, row in ohlcv.iterrows():
        candle_low = float(row["low"])
        candle_high = float(row["high"])
        candle_vol = float(row["volume"])
        candle_range = candle_high - candle_low

        if candle_range == 0 or candle_vol == 0:
            # Point candle — assign to nearest bin
            idx = np.searchsorted(bin_edges, candle_low, side="right") - 1
            idx = max(0, min(idx, bins - 1))
            bin_volume[idx] += candle_vol
            continue

        for b in range(bins):
            bin_low = bin_edges[b]
            bin_high = bin_edges[b + 1]
            # Overlap between candle range and bin range
            overlap_low = max(candle_low, bin_low)
            overlap_high = min(candle_high, bin_high)
            if overlap_high > overlap_low:
                overlap_pct = (overlap_high - overlap_low) / candle_range
                bin_volume[b] += candle_vol * overlap_pct

    total_volume = bin_volume.sum()
    if total_volume == 0:
        mid = (price_min + price_max) / 2
        return VolumeProfile(poc=mid, vah=mid, val=mid, total_volume=0.0)

    # POC = bin with highest volume
    poc_idx = int(np.argmax(bin_volume))
    poc = float(bin_centers[poc_idx])

    # Value Area: expand from POC outward until value_area_pct of volume captured
    target_vol = total_volume * value_area_pct
    cumvol = bin_volume[poc_idx]
    lo_idx = poc_idx
    hi_idx = poc_idx

    while cumvol < target_vol:
        # Expand to the side with more volume
        can_expand_lo = lo_idx > 0
        can_expand_hi = hi_idx < bins - 1

        if not can_expand_lo and not can_expand_hi:
            break

        vol_lo = bin_volume[lo_idx - 1] if can_expand_lo else -1
        vol_hi = bin_volume[hi_idx + 1] if can_expand_hi else -1

        if vol_hi >= vol_lo:
            hi_idx += 1
            cumvol += bin_volume[hi_idx]
        else:
            lo_idx -= 1
            cumvol += bin_volume[lo_idx]

    vah = float(bin_edges[hi_idx + 1])
    val = float(bin_edges[lo_idx])

    return VolumeProfile(poc=poc, vah=vah, val=val, total_volume=total_volume)
