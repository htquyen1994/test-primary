"""
SMC Analysis Module — Smart Money Concepts
============================================
Detects institutional price structure:
  - Order Block (OB): last opposing candle before a strong impulse move
  - Fair Value Gap (FVG): three-candle imbalance (wick gap)
  - Change of Character (CHoCH): break of the most recent swing high/low
  - HTF Bias: Higher-Timeframe trend direction (HH/HL or LH/LL)

Scoring (max 30 pts):
  CHoCH aligned with 1H bias:  +10 pts
  Order Block retest:          +10 pts
  FVG midpoint touched:        +10 pts

Satisfies: Requirements 1.2, 6.2 (SMC component)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from indicators.atr import ATR

logger = logging.getLogger(__name__)

# Minimum impulse body as multiple of ATR to qualify as OB trigger
OB_ATR_MULTIPLIER = 1.5
# Lookback window for swing high/low detection
SWING_LOOKBACK = 20
# Tolerance for FVG midpoint touch (% of price)
FVG_TOUCH_TOLERANCE = 0.001  # 0.1%
# Tolerance for OB retest (price must be within OB zone)
OB_RETEST_TOLERANCE = 0.002  # 0.2% beyond OB boundary


@dataclass
class OrderBlock:
    """Represents a bullish or bearish Order Block zone."""
    type: str           # "bullish" | "bearish"
    high: float
    low: float
    mid: float
    candle_index: int   # index of the OB candle in the DataFrame
    valid: bool = True  # False when price closes beyond the OB zone

    def is_price_retesting(self, current_price: float) -> bool:
        """
        Returns True if current_price is within or just touching the OB zone.
        Allows a small tolerance beyond the boundary.
        """
        tolerance = self.mid * OB_RETEST_TOLERANCE
        return (self.low - tolerance) <= current_price <= (self.high + tolerance)

    def invalidate_if_broken(self, candle: pd.Series) -> None:
        """
        Invalidate OB if price closes beyond the zone.
        Bullish OB: invalidated when close < low
        Bearish OB: invalidated when close > high
        """
        if self.type == "bullish" and float(candle["close"]) < self.low:
            self.valid = False
        elif self.type == "bearish" and float(candle["close"]) > self.high:
            self.valid = False


@dataclass
class FairValueGap:
    """Represents a bullish or bearish Fair Value Gap (imbalance zone)."""
    type: str       # "bullish" | "bearish"
    top: float      # upper boundary of the gap
    bot: float      # lower boundary of the gap
    mid: float      # midpoint of the gap
    candle_index: int
    filled: bool = False

    def is_price_at_midpoint(self, current_price: float) -> bool:
        """Returns True if price is within tolerance of the FVG midpoint."""
        tolerance = self.mid * FVG_TOUCH_TOLERANCE
        return abs(current_price - self.mid) <= tolerance

    def check_if_filled(self, candle: pd.Series) -> None:
        """Mark FVG as filled when price trades through the full gap."""
        if self.type == "bullish" and float(candle["low"]) <= self.bot:
            self.filled = True
        elif self.type == "bearish" and float(candle["high"]) >= self.top:
            self.filled = True


@dataclass
class CHoCH:
    """Represents a Change of Character event."""
    direction: str      # "bullish" | "bearish"
    break_price: float  # the swing level that was broken
    candle_index: int


@dataclass
class SMCResult:
    """Output of the SMC analysis for a single candle."""
    score: float = 0.0
    order_block: Optional[OrderBlock] = None        # best OB (closest to price)
    order_blocks: list = field(default_factory=list)  # all valid OBs (up to 3)
    fvg: Optional[FairValueGap] = None
    choch: Optional[CHoCH] = None
    htf_bias: str = "neutral"   # "bullish" | "bearish" | "neutral"
    ob_retested: bool = False
    fvg_touched: bool = False
    choch_aligned: bool = False


# ---------------------------------------------------------------------------
# Core detection functions
# ---------------------------------------------------------------------------

def find_order_block(
    ohlcv: pd.DataFrame,
    atr_multiplier: float = OB_ATR_MULTIPLIER,
    max_obs: int = 3,
) -> list:
    """
    Identify up to `max_obs` most recent valid Order Blocks.

    Algorithm:
    1. Scan backwards from the last candle
    2. Find impulse candles whose body >= atr_multiplier * ATR(14)
    3. The OB is the last opposing candle immediately before the impulse
    4. Return up to max_obs valid OBs, sorted by proximity to current price
    5. Prioritize OBs that coincide with Fibonacci levels (61.8%, 50%)

    Bullish OB: bearish candle before a bullish impulse
    Bearish OB: bullish candle before a bearish impulse

    Returns:
        List[OrderBlock] — up to max_obs valid OBs, sorted by proximity to price.
        Empty list if none found.

    Satisfies: Requirement 1.2 (OB mathematical logic), Task 30.2
    """
    n = len(ohlcv)
    if n < 16:  # need at least ATR(14) + 2 candles
        return []

    atr_series = ATR().compute(ohlcv, period=14)
    atr_val = atr_series.iloc[-1]
    if np.isnan(atr_val) or atr_val == 0:
        return []

    current_price = float(ohlcv.iloc[-1]["close"])

    # Compute Fibonacci levels for prioritization
    fib_levels = _compute_fib_levels(ohlcv)

    found_obs: list = []

    # Scan backwards — skip last candle (still forming in live mode)
    # Limit to last 100 candles to keep O(n) instead of O(n²)
    for i in range(n - 2, max(0, n - 102), -1):
        if len(found_obs) >= max_obs:
            break

        impulse_candle = ohlcv.iloc[i + 1] if i + 1 < n else None
        if impulse_candle is None:
            continue

        impulse_body = abs(float(impulse_candle["close"]) - float(impulse_candle["open"]))
        if impulse_body < atr_multiplier * atr_val:
            continue

        ob_candle = ohlcv.iloc[i]
        ob_high = float(ob_candle["high"])
        ob_low = float(ob_candle["low"])
        ob_mid = (ob_high + ob_low) / 2.0

        ob_type = None
        # Bullish impulse → bearish OB candle before it
        if (float(impulse_candle["close"]) > float(impulse_candle["open"]) and
                float(ob_candle["close"]) < float(ob_candle["open"])):
            ob_type = "bullish"
        # Bearish impulse → bullish OB candle before it
        elif (float(impulse_candle["close"]) < float(impulse_candle["open"]) and
              float(ob_candle["close"]) > float(ob_candle["open"])):
            ob_type = "bearish"

        if ob_type is None:
            continue

        ob = OrderBlock(
            type=ob_type,
            high=ob_high,
            low=ob_low,
            mid=ob_mid,
            candle_index=i,
        )
        # Validate: OB must not have been broken by subsequent candles
        for j in range(i + 1, n):
            ob.invalidate_if_broken(ohlcv.iloc[j])

        if ob.valid:
            # Check Fibonacci confluence — prioritize OBs near 61.8% or 50%
            ob_fib_score = _ob_fib_score(ob, fib_levels)
            found_obs.append((ob, ob_fib_score))

    if not found_obs:
        return []

    # Sort: Fibonacci-aligned OBs first, then by proximity to current price
    found_obs.sort(key=lambda x: (-x[1], abs(x[0].mid - current_price)))
    return [ob for ob, _ in found_obs]


def _compute_fib_levels(ohlcv: pd.DataFrame, lookback: int = 50) -> dict:
    """
    Compute Fibonacci retracement levels for OB prioritization.

    Uses pivot highs/lows (local extremes) rather than absolute max/min to
    avoid spurious Fibonacci levels from isolated wicks far from price structure.
    Falls back to absolute extremes if not enough pivots are detected.
    """
    n = len(ohlcv)
    if n < 4:
        return {}
    recent = ohlcv.iloc[-min(lookback, n):]
    nr = len(recent)

    # Detect pivot highs and lows (requires 2-bar confirmation on each side)
    _highs = recent["high"].values.astype(float)
    _lows = recent["low"].values.astype(float)
    pivot_highs = [
        _highs[i] for i in range(2, nr - 2)
        if _highs[i] > _highs[i - 1] and _highs[i] > _highs[i - 2]
        and _highs[i] > _highs[i + 1] and _highs[i] > _highs[i + 2]
    ]
    pivot_lows = [
        _lows[i] for i in range(2, nr - 2)
        if _lows[i] < _lows[i - 1] and _lows[i] < _lows[i - 2]
        and _lows[i] < _lows[i + 1] and _lows[i] < _lows[i + 2]
    ]

    if pivot_highs and pivot_lows:
        swing_high = max(pivot_highs)
        swing_low = min(pivot_lows)
    else:
        # Fallback: absolute extremes when pivots are insufficient
        swing_high = float(recent["high"].max())
        swing_low = float(recent["low"].min())

    diff = swing_high - swing_low
    if diff == 0:
        return {}
    return {
        "618": swing_high - 0.618 * diff,
        "500": swing_high - 0.500 * diff,
        "382": swing_high - 0.382 * diff,
    }


def _ob_fib_score(ob: OrderBlock, fib_levels: dict) -> int:
    """Return a priority score based on Fibonacci confluence (higher = better)."""
    tolerance = ob.mid * 0.005  # 0.5%
    if abs(ob.mid - fib_levels.get("618", -1)) <= tolerance:
        return 3
    if abs(ob.mid - fib_levels.get("500", -1)) <= tolerance:
        return 2
    if abs(ob.mid - fib_levels.get("382", -1)) <= tolerance:
        return 1
    return 0


def find_fvg(ohlcv: pd.DataFrame) -> Optional[FairValueGap]:
    """
    Identify the most recent unfilled Fair Value Gap.

    FVG = three-candle imbalance where:
    - Bullish FVG: candle[i-2].high < candle[i].low  (gap above)
    - Bearish FVG: candle[i-2].low  > candle[i].high (gap below)

    Scans backwards to find the most recent unfilled FVG.

    Satisfies: Requirement 1.2 (FVG mathematical logic)
    """
    n = len(ohlcv)
    if n < 3:
        return None

    # Scan backwards (most recent first)
    for i in range(n - 1, 1, -1):
        c1 = ohlcv.iloc[i - 2]
        c3 = ohlcv.iloc[i]

        c1_high = float(c1["high"])
        c1_low = float(c1["low"])
        c3_high = float(c3["high"])
        c3_low = float(c3["low"])

        # Bullish FVG: gap between c1.high and c3.low
        if c1_high < c3_low:
            fvg = FairValueGap(
                type="bullish",
                top=c3_low,
                bot=c1_high,
                mid=(c3_low + c1_high) / 2.0,
                candle_index=i,
            )
            # Check if filled by any subsequent candle
            for j in range(i + 1, n):
                fvg.check_if_filled(ohlcv.iloc[j])
            if not fvg.filled:
                return fvg

        # Bearish FVG: gap between c3.high and c1.low
        elif c1_low > c3_high:
            fvg = FairValueGap(
                type="bearish",
                top=c1_low,
                bot=c3_high,
                mid=(c1_low + c3_high) / 2.0,
                candle_index=i,
            )
            for j in range(i + 1, n):
                fvg.check_if_filled(ohlcv.iloc[j])
            if not fvg.filled:
                return fvg

    return None


def detect_htf_bias(ohlcv_1h: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> str:
    """
    Classify 1H trend as "bullish", "bearish", or "neutral".

    Uses Higher High / Higher Low (HH/HL) and Lower High / Lower Low (LH/LL)
    market structure from the price-action skill.

    Satisfies: Requirement 1.4 (Context Filter — HTF bias)
    """
    n = len(ohlcv_1h)
    if n < 4:
        return "neutral"

    recent = ohlcv_1h.iloc[-min(lookback, n):]
    highs = recent["high"].values.astype(float)
    lows = recent["low"].values.astype(float)

    # Find pivot highs and lows (simple: local max/min with 2-bar lookback)
    pivot_highs = []
    pivot_lows = []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            pivot_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            pivot_lows.append(lows[i])

    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        # Fallback: compare first half vs second half
        mid = len(recent) // 2
        first_close = recent["close"].iloc[:mid].mean()
        second_close = recent["close"].iloc[mid:].mean()
        if second_close > first_close * 1.002:
            return "bullish"
        elif second_close < first_close * 0.998:
            return "bearish"
        return "neutral"

    # HH + HL = bullish; LH + LL = bearish
    hh = pivot_highs[-1] > pivot_highs[-2]
    hl = pivot_lows[-1] > pivot_lows[-2]
    lh = pivot_highs[-1] < pivot_highs[-2]
    ll = pivot_lows[-1] < pivot_lows[-2]

    if hh and hl:
        return "bullish"
    elif lh and ll:
        return "bearish"
    return "neutral"


def detect_choch(ohlcv: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> Optional[CHoCH]:
    """
    Detect Change of Character (CHoCH) — break of the most recent swing.

    Bullish CHoCH: last close breaks above the highest high in the lookback window
                   (excluding the last candle itself)
    Bearish CHoCH: last close breaks below the lowest low in the lookback window
                   (excluding the last candle itself)

    Satisfies: Requirement 6.2 (SMC component — CHoCH)
    """
    n = len(ohlcv)
    if n < 5:
        return None

    # Use all candles except the last one as the reference window
    reference = ohlcv.iloc[-min(lookback, n):-1]
    if len(reference) < 2:
        return None

    swing_high = float(reference["high"].max())
    swing_low = float(reference["low"].min())

    last_candle = ohlcv.iloc[-1]
    last_close = float(last_candle["close"])
    last_idx = n - 1

    # Bullish CHoCH: close breaks above swing high with 0.1% momentum buffer
    # Prevents false signals from candles that barely graze the swing level.
    if last_close > swing_high * (1 + 0.001):
        return CHoCH(
            direction="bullish",
            break_price=swing_high,
            candle_index=last_idx,
        )

    # Bearish CHoCH: close breaks below swing low with 0.1% momentum buffer
    if last_close < swing_low * (1 - 0.001):
        return CHoCH(
            direction="bearish",
            break_price=swing_low,
            candle_index=last_idx,
        )

    return None


def _aligned_with_bias(choch_direction: str, htf_bias: str) -> bool:
    """Returns True if CHoCH direction aligns with HTF bias."""
    if htf_bias == "neutral":
        return False
    return choch_direction == htf_bias


# ---------------------------------------------------------------------------
# Score aggregator
# ---------------------------------------------------------------------------

def compute_smc_score(
    ohlcv_15m: pd.DataFrame,
    ohlcv_1h: pd.DataFrame,
    atr_multiplier: float = OB_ATR_MULTIPLIER,
    signal_direction: str = "long",
    htf_bias: Optional[str] = None,
) -> SMCResult:
    """
    Compute the SMC module score (max 30 pts).

    Scoring:
        CHoCH aligned with 1H bias:  +10 pts
        Order Block retest:          +10 pts  (only OBs aligned with signal_direction)
        FVG midpoint touched:        +10 pts

    Args:
        ohlcv_15m:        15-minute OHLCV DataFrame (trigger timeframe)
        ohlcv_1h:         1-hour OHLCV DataFrame (context timeframe)
        atr_multiplier:   Minimum impulse body as multiple of ATR
        signal_direction: "long" or "short" — only matching OBs are scored.
                          Bullish OBs act as support for longs;
                          Bearish OBs act as resistance for shorts.

    Returns:
        SMCResult with score and detected patterns

    Satisfies: Requirement 6.2 (SMC component)
    """
    result = SMCResult()

    if ohlcv_15m.empty or len(ohlcv_15m) < 5:
        return result

    current_price = float(ohlcv_15m.iloc[-1]["close"])

    # 1. HTF bias — use caller-provided value to avoid recomputing when already known
    result.htf_bias = htf_bias if htf_bias is not None else (
        detect_htf_bias(ohlcv_1h) if not ohlcv_1h.empty else "neutral"
    )

    # 2. CHoCH detection
    choch = detect_choch(ohlcv_15m)
    result.choch = choch
    if choch and _aligned_with_bias(choch.direction, result.htf_bias):
        result.choch_aligned = True
        result.score += 10.0

    # 3. Order Block retest — only score OBs that align with signal direction.
    #    Bullish OB = demand zone (support) → valid for long signals only.
    #    Bearish OB = supply zone (resistance) → valid for short signals only.
    expected_ob_type = "bullish" if signal_direction == "long" else "bearish"
    obs = find_order_block(ohlcv_15m, atr_multiplier)
    result.order_blocks = obs
    # Best OB = first in list (sorted by Fib priority then proximity)
    result.order_block = obs[0] if obs else None
    for ob in obs:
        if ob.valid and ob.is_price_retesting(current_price) and ob.type == expected_ob_type:
            result.ob_retested = True
            result.order_block = ob  # use the retesting OB as primary
            result.score += 10.0
            break  # score only once even if multiple OBs are retested

    # 4. FVG midpoint touch
    fvg = find_fvg(ohlcv_15m)
    result.fvg = fvg
    if fvg and not fvg.filled and fvg.is_price_at_midpoint(current_price):
        result.fvg_touched = True
        result.score += 10.0

    result.score = min(result.score, 30.0)
    return result
