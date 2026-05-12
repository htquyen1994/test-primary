"""
Audit Client
=============
Lightweight Redis publisher for audit events.
Used by ScoringService and TradeExecutor to emit scoring and trade events
to mock-exchange-workspace for analysis.

All methods are fire-and-forget — never raise exceptions to callers.
Transport: Redis list `audit:pending_snapshots` (RPUSH/BLPOP pattern).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

AUDIT_QUEUE_KEY = "audit:pending_snapshots"


class AuditClient:
    """
    Publishes audit events to Redis list consumed by mock-exchange-workspace.
    Safe to use in hot paths — all failures are logged and swallowed.
    """

    def __init__(self, redis_client, enabled: bool = True) -> None:
        self._r = redis_client
        self._enabled = enabled

    def emit(self, event_type: str, payload: dict) -> None:
        if not self._enabled:
            return
        try:
            self._r.rpush(AUDIT_QUEUE_KEY, json.dumps({"type": event_type, **payload}))
        except Exception as exc:
            logger.warning("AuditClient emit failed [%s]: %s", event_type, exc)

    def emit_trade_opened(
        self,
        signal_id: Optional[str],
        order_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        amount: float,
        leverage: int,
        sl: float,
        tp1: float,
        tp2: Optional[float] = None,
    ) -> None:
        self.emit("trade_opened", {
            "signal_id": signal_id,
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "amount": amount,
            "leverage": leverage,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
        })

    def emit_trade_closed(
        self,
        order_id: str,
        exit_price: float,
        exit_reason: str,
    ) -> None:
        self.emit("trade_closed", {
            "order_id": order_id,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
        })
