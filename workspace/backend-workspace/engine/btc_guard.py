"""
BTC Volatility Spike Guard — Black Swan Protection
=====================================================
Monitors BTC/USDT 15m candles for sudden moves and protects Alt positions.

3 Spike Scenarios (Task 33.2):
  BTC dump > 2%/15m:
    → Cancel ALL Alt alerts
    → Push warning to open Alt long positions: "⚠ BTC spike down — review SL"
    → Reset delta for all Alt symbols
    → Cooldown: 30 minutes

  BTC pump > 2%/15m:
    → Reduce size 50% for all new Alt long signals
    → If Alt gain < 0.3× BTC gain → block Alt long completely (relative weakness)
    → Cooldown: 30 minutes

  Cooldown period (0-30 min after spike):
    → All Alt alerts suppressed regardless of score
    → Log reason: "BTC_SPIKE_COOLDOWN"

Spike threshold: |close - open| / open > 2% in single 15m candle

State stored in Redis: `btc_guard:spike` with TTL = cooldown duration

Satisfies: Requirements 23 (Phase 9 BTC Spike Guard)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd

from trading_core.cache import get_redis, RedisKeys

logger = logging.getLogger(__name__)

# Spike detection threshold
SPIKE_THRESHOLD_PCT = 0.02
COOLDOWN_MINUTES = 30
RELATIVE_WEAKNESS_RATIO = 0.3

BTC_SYMBOL = "BTC/USDT"
REDIS_SPIKE_TTL = COOLDOWN_MINUTES * 60 + 60


@dataclass
class BTCSpikeResult:
    """Result of BTC spike check."""
    spike_detected: bool = False
    direction: Optional[str] = None     # "dump" | "pump" | None
    magnitude_pct: float = 0.0          # absolute % move
    cooldown_until: Optional[datetime] = None
    in_cooldown: bool = False           # True if within cooldown window
    size_multiplier: float = 1.0        # 1.0 | 0.5 | 0.0
    block_reason: Optional[str] = None


class BTCVolatilityGuard:
    """
    Monitors BTC volatility and applies protective filters to Alt signals.

    Usage:
        guard = BTCVolatilityGuard()
        result = guard.check_btc_spike(ohlcv_btc_15m)
        if result.in_cooldown:
            return  # suppress Alt alert
    """

    def __init__(self) -> None:
        pass  # singleton provided by trading_core

    def _get_redis(self):
        return get_redis()

    def check_btc_spike(self, ohlcv_btc_15m: pd.DataFrame) -> BTCSpikeResult:
        """
        Check if BTC had a spike in the most recent 15m candle.

        Args:
            ohlcv_btc_15m: BTC/USDT 15m OHLCV DataFrame

        Returns:
            BTCSpikeResult with spike info and size multiplier
        """
        # First check if we're already in cooldown
        cooldown_result = self._check_cooldown()
        if cooldown_result.in_cooldown:
            return cooldown_result

        if ohlcv_btc_15m.empty or len(ohlcv_btc_15m) < 2:
            return BTCSpikeResult()

        # Check the most recent closed candle (second to last — last is still forming)
        last_candle = ohlcv_btc_15m.iloc[-2] if len(ohlcv_btc_15m) >= 2 else ohlcv_btc_15m.iloc[-1]
        open_price = float(last_candle["open"])
        close_price = float(last_candle["close"])

        if open_price == 0:
            return BTCSpikeResult()

        move_pct = (close_price - open_price) / open_price
        magnitude = abs(move_pct)

        if magnitude < SPIKE_THRESHOLD_PCT:
            return BTCSpikeResult()

        # Spike detected
        direction = "dump" if move_pct < 0 else "pump"
        cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=COOLDOWN_MINUTES)

        # Store spike state in Redis
        self._store_spike(direction, magnitude, cooldown_until)

        # Publish spike event
        self._publish_spike_event(direction, magnitude, cooldown_until)

        logger.warning(
            "🚨 BTC SPIKE DETECTED: %s %.2f%% | Cooldown until %s",
            direction.upper(), magnitude * 100, cooldown_until.isoformat(),
        )

        return BTCSpikeResult(
            spike_detected=True,
            direction=direction,
            magnitude_pct=magnitude,
            cooldown_until=cooldown_until,
            in_cooldown=True,
            size_multiplier=0.0 if direction == "dump" else 0.5,
            block_reason=f"BTC_{direction.upper()}_SPIKE_{magnitude*100:.1f}PCT",
        )

    def check_alt_signal(
        self,
        alt_symbol: str,
        alt_gain_pct: float,
        signal_direction: str,
    ) -> BTCSpikeResult:
        """
        Check if an Alt signal should be filtered based on BTC spike state.

        Args:
            alt_symbol:       Alt symbol (e.g., "ETH/USDT")
            alt_gain_pct:     Alt price change % in same 15m window as BTC spike
            signal_direction: "long" | "short"

        Returns:
            BTCSpikeResult with size_multiplier and block_reason
        """
        if alt_symbol == BTC_SYMBOL:
            return BTCSpikeResult()  # BTC itself is not filtered

        # Check cooldown
        cooldown_result = self._check_cooldown()
        if not cooldown_result.in_cooldown:
            return BTCSpikeResult()

        spike_data = self._get_spike_data()
        if not spike_data:
            return BTCSpikeResult()

        direction = spike_data.get("direction")
        btc_magnitude = spike_data.get("magnitude_pct", 0.0)

        # BTC dump scenario
        if direction == "dump":
            return BTCSpikeResult(
                spike_detected=True,
                direction="dump",
                magnitude_pct=btc_magnitude,
                in_cooldown=True,
                size_multiplier=0.0,
                block_reason="BTC_SPIKE_COOLDOWN",
            )

        # BTC pump scenario
        if direction == "pump" and signal_direction == "long":
            # Check relative weakness: Alt gain < 0.3× BTC gain → block
            if btc_magnitude > 0 and alt_gain_pct < btc_magnitude * RELATIVE_WEAKNESS_RATIO:
                return BTCSpikeResult(
                    spike_detected=True,
                    direction="pump",
                    magnitude_pct=btc_magnitude,
                    in_cooldown=True,
                    size_multiplier=0.0,
                    block_reason=f"BTC_PUMP_ALT_WEAKNESS: {alt_symbol} gain {alt_gain_pct*100:.1f}% < {RELATIVE_WEAKNESS_RATIO*100:.0f}% of BTC {btc_magnitude*100:.1f}%",
                )
            # Alt is following BTC pump — reduce size 50%
            return BTCSpikeResult(
                spike_detected=True,
                direction="pump",
                magnitude_pct=btc_magnitude,
                in_cooldown=True,
                size_multiplier=0.5,
                block_reason=None,  # Not blocked, just reduced
            )

        return BTCSpikeResult(in_cooldown=True, size_multiplier=1.0)

    def cancel_all_alt_alerts(self) -> None:
        """Cancel all active Alt alerts when BTC dumps."""
        r = self._get_redis()
        r.publish(RedisKeys.Channels.CANCEL_ALL_ALERTS, json.dumps({
            "reason": "BTC_SPIKE_DOWN",
            "message": "⚠ BTC spike down — all Alt alerts cancelled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        logger.warning("All Alt alerts cancelled due to BTC spike down")

    def reset_alt_deltas(self, symbols: list) -> None:
        """Reset delta for all Alt symbols after BTC dump (data no longer valid)."""
        r = self._get_redis()
        for symbol in symbols:
            if symbol != BTC_SYMBOL:
                r.set(RedisKeys.delta(symbol), "0", ex=300)
        logger.info("Delta reset for %d Alt symbols after BTC spike", len(symbols))

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _check_cooldown(self) -> BTCSpikeResult:
        """Check if we're currently in a BTC spike cooldown period."""
        spike_data = self._get_spike_data()
        if not spike_data:
            return BTCSpikeResult(in_cooldown=False)

        cooldown_until_str = spike_data.get("cooldown_until")
        if not cooldown_until_str:
            return BTCSpikeResult(in_cooldown=False)

        cooldown_until = datetime.fromisoformat(cooldown_until_str)
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if now < cooldown_until:
            return BTCSpikeResult(
                spike_detected=True,
                direction=spike_data.get("direction"),
                magnitude_pct=spike_data.get("magnitude_pct", 0.0),
                cooldown_until=cooldown_until,
                in_cooldown=True,
                size_multiplier=0.0 if spike_data.get("direction") == "dump" else 0.5,
                block_reason="BTC_SPIKE_COOLDOWN",
            )

        return BTCSpikeResult(in_cooldown=False)

    def _get_spike_data(self) -> Optional[dict]:
        """Get spike data from Redis."""
        try:
            r = self._get_redis()
            raw = r.get(RedisKeys.btc_guard_spike())
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def _store_spike(self, direction: str, magnitude: float, cooldown_until: datetime) -> None:
        """Store spike state in Redis with TTL."""
        try:
            r = self._get_redis()
            r.set(RedisKeys.btc_guard_spike(), json.dumps({
                "direction": direction,
                "magnitude_pct": magnitude,
                "cooldown_until": cooldown_until.isoformat(),
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }), ex=REDIS_SPIKE_TTL)
        except Exception as exc:
            logger.warning("Failed to store spike state: %s", exc)

    def _publish_spike_event(self, direction: str, magnitude: float, cooldown_until: datetime) -> None:
        """Publish BTC spike event to Redis for frontend notification."""
        try:
            r = self._get_redis()
            r.publish(RedisKeys.Channels.BTC_SPIKE, json.dumps({
                "event": "btc_spike",
                "direction": direction,
                "magnitude_pct": magnitude,
                "cooldown_until": cooldown_until.isoformat(),
                "message": (
                    f"⚠ BTC {'dump' if direction == 'dump' else 'pump'} "
                    f"{magnitude*100:.1f}% — Alt alerts {'cancelled' if direction == 'dump' else 'reduced 50%'}"
                ),
            }))
        except Exception as exc:
            logger.warning("Failed to publish spike event: %s", exc)
