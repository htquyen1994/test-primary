"""
Redis Pub/Sub Alert Sender
===========================
Publishes ALERT-class Signal Cards to Redis channel for Dashboard consumption.

Only signals with classification == "ALERT" and final_score >= threshold are published.

Satisfies: Requirements 6.5, 18.10
"""

from __future__ import annotations

import json
import logging

from strategies.signal import Signal
from alert.builder import build_signal_card

logger = logging.getLogger(__name__)

ALERTS_CHANNEL = "alerts:channel"


async def publish_alert(
    redis_client,
    signal: Signal,
    fee_rate: float = 0.001,
    slippage_pct: float = 0.0002,
) -> bool:
    """
    Build and publish a Signal Card to Redis pub/sub.

    Only publishes if classification == "ALERT".
    Returns True if published, False if skipped.

    Satisfies: Requirements 6.5, 18.10
    """
    if signal.classification != "ALERT":
        logger.debug(
            "Signal not published (classification=%s, score=%d): %s %s",
            signal.classification, signal.final_score,
            signal.asset, signal.direction,
        )
        return False

    card = build_signal_card(signal, fee_rate=fee_rate, slippage_pct=slippage_pct)
    payload = json.dumps(card)

    await redis_client.publish(ALERTS_CHANNEL, payload)
    logger.info(
        "Alert published: %s %s score=%d expires_at=%d",
        signal.asset, signal.direction,
        signal.final_score, signal.expires_at_candle,
    )
    return True
