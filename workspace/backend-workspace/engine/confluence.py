"""
Confluence Bonus Calculator
=============================
Bonus points when multiple technical layers converge at the same price zone.

Bonus table (raw points, normalized via /125*100 in scorer):
  OB + Fib 38.2%:           +15 pts
  OB + Fib 50%:             +25 pts
  OB + Fib 61.8%:           +35 pts
  OB + Fib 61.8% + FVG:     +45 pts  (POC check removed — belongs in VSA module)

The bonus is capped at 15 pts in the scorer formula (max raw = 125).

Note (Task 30.3): POC confluence was removed from this module.
POC proximity bonus belongs ONLY in compute_vsa_score() (VSA module).
This prevents double-counting the same POC signal in both modules.

Satisfies: Requirement 6.2 (Confluence Bonus)
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

from engine.smc import OrderBlock, FairValueGap

logger = logging.getLogger(__name__)

CONFLUENCE_TOLERANCE_PCT = 0.005  # 0.5% tolerance for level alignment

# Fibonacci bonus points
FIB_BONUS = {"618": 35, "500": 25, "382": 15, "786": 10}


def calc_fibonacci(ohlcv: pd.DataFrame, lookback: int = 50) -> dict:
    """
    Calculate Fibonacci retracement levels from the most recent swing.

    Returns dict with keys "382", "500", "618", "786" and price values.
    """
    n = len(ohlcv)
    if n < 4:
        return {}

    recent = ohlcv.iloc[-min(lookback, n):]
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    diff = swing_high - swing_low

    if diff == 0:
        return {}

    return {
        "382": swing_high - 0.382 * diff,
        "500": swing_high - 0.500 * diff,
        "618": swing_high - 0.618 * diff,
        "786": swing_high - 0.786 * diff,
    }


def compute_confluence_bonus(
    ohlcv: pd.DataFrame,
    ob_or_obs,
    fvg: Optional[FairValueGap],
    poc: float = 0.0,
    lookback: int = 50,
) -> float:
    """
    Compute confluence bonus (max 15 pts in normalized formula).

    Checks OB + Fibonacci + FVG confluence only.
    POC check has been REMOVED (Task 30.3) — POC belongs in compute_vsa_score().

    Args:
        ohlcv:      15m OHLCV DataFrame
        ob_or_obs:  Single OrderBlock OR List[OrderBlock] (Task 30.2 compatibility)
        fvg:        Detected Fair Value Gap (or None)
        poc:        Ignored — kept for API compatibility only (POC moved to VSA)
        lookback:   Fibonacci lookback window

    Returns:
        Bonus score in [0, 15] (already normalized for use in scorer)

    Satisfies: Requirement 6.2 (Confluence Bonus)
    """
    # Normalize input: accept both single OB and list of OBs (Task 30.2)
    if ob_or_obs is None:
        return 0.0
    if isinstance(ob_or_obs, list):
        obs = [o for o in ob_or_obs if o is not None and o.valid]
    else:
        obs = [ob_or_obs] if ob_or_obs.valid else []

    if not obs:
        return 0.0

    fib_levels = calc_fibonacci(ohlcv, lookback)
    if not fib_levels:
        return 0.0

    best_bonus = 0.0

    for ob in obs:
        threshold = ob.mid * CONFLUENCE_TOLERANCE_PCT
        bonus = 0.0

        # Fibonacci confluence (take the highest matching level)
        for level_key, pts in FIB_BONUS.items():
            fib_price = fib_levels.get(level_key, 0)
            if fib_price == 0:
                continue
            in_ob = ob.low <= fib_price <= ob.high
            near_mid = abs(fib_price - ob.mid) <= threshold
            if in_ob or near_mid:
                bonus += pts
                break  # take the strongest match only

        # FVG confluence (+10 pts) — POC removed (Task 30.3)
        if fvg and not fvg.filled and abs(fvg.mid - ob.mid) <= threshold:
            bonus += 10.0

        if bonus > best_bonus:
            best_bonus = bonus

    # Normalize: raw bonus max = 45 (35 Fib + 10 FVG), cap at 15 for scorer formula
    normalized = min(best_bonus / 45.0 * 15.0, 15.0)
    return normalized
