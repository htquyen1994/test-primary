"""
Time-based Invalidation
========================
Manages signal expiry based on candle count.

Rules:
  - Hard expiry: signal expires after time_invalidation_candles (default 15)
  - Soft expiry: expires immediately if HTF bias reverses after 5 candles
  - Degraded: score reduced if price stuck in OB for > 8 candles

Satisfies: Requirements 18.5, 17.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from strategies.signal import Signal

logger = logging.getLogger(__name__)

HARD_EXPIRY_CANDLES = 15
SOFT_EXPIRY_CANDLES = 5
SIDEWAYS_PENALTY_CANDLES = 8
SIDEWAYS_SCORE_PENALTY = 20


@dataclass
class InvalidationResult:
    """Result of a time invalidation check."""
    status: str         # "ACTIVE" | "EXPIRED" | "CANCELLED" | "DEGRADED"
    reason: str = ""
    updated_score: Optional[int] = None


def compute_expiry(candle_index: int, invalidation_candles: int = HARD_EXPIRY_CANDLES) -> int:
    """
    Compute the candle index at which a signal expires.

    Args:
        candle_index:         Current candle index when signal was created
        invalidation_candles: Number of candles before expiry (default 15)

    Returns:
        Candle index at which the signal expires

    Satisfies: Requirement 18.5
    """
    return candle_index + invalidation_candles


def is_expired(signal: Signal, current_candle_index: int) -> bool:
    """
    Returns True if the signal has passed its expiry candle.

    Satisfies: Requirement 18.5
    """
    return current_candle_index > signal.expires_at_candle


def check_time_invalidation(
    signal: Signal,
    current_candle_index: int,
    htf_bias_changed: bool = False,
    no_directional_momentum: bool = False,
) -> InvalidationResult:
    """
    Check if a signal should be invalidated based on time rules.

    Args:
        signal:                  The signal to check
        current_candle_index:    Current candle index
        htf_bias_changed:        True if 1H bias has reversed since signal creation
        no_directional_momentum: True if price has been stuck in OB zone

    Returns:
        InvalidationResult with status and reason

    Satisfies: Requirements 18.5, 17.4
    """
    candles_elapsed = current_candle_index - signal.candle_index

    # Hard expiry: 15 candles = 225 minutes for 15m timeframe
    if candles_elapsed > HARD_EXPIRY_CANDLES:
        return InvalidationResult(
            status="EXPIRED",
            reason=f"Time limit exceeded ({candles_elapsed} candles > {HARD_EXPIRY_CANDLES})",
        )

    # Soft expiry: 5 candles + HTF bias reversed
    if candles_elapsed > SOFT_EXPIRY_CANDLES and htf_bias_changed:
        return InvalidationResult(
            status="CANCELLED",
            reason="HTF bias reversed after signal creation",
        )

    # Sideways penalty: reduce score if no momentum
    if candles_elapsed > SIDEWAYS_PENALTY_CANDLES and no_directional_momentum:
        new_score = max(0, signal.final_score - SIDEWAYS_SCORE_PENALTY)
        if new_score < 55:  # below WATCH threshold
            return InvalidationResult(
                status="DEGRADED",
                reason=f"No directional momentum after {candles_elapsed} candles",
                updated_score=new_score,
            )

    return InvalidationResult(status="ACTIVE")


def record_expiry(signal: Signal, current_price: float) -> dict:
    """
    Build an expiry record for the Signal_Log.

    Satisfies: Requirement 17.4
    """
    return {
        "log_id": None,  # will be set by signal log writer
        "user_action": "EXPIRED",
        "expiry_price": current_price,
        "skip_reason": f"Signal expired at candle {signal.expires_at_candle}",
    }
