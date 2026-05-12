"""
AuditConsumer — Redis BLPOP loop that dispatches audit events.
Dispatches to SignalAuditor, TradeAuditor based on event type.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audit.signal_auditor import SignalAuditor
    from audit.trade_auditor import TradeAuditor

logger = logging.getLogger(__name__)

_QUEUE_KEY = "audit:pending_snapshots"


class AuditConsumer:
    """
    Background coroutine: BLPOP audit:pending_snapshots → dispatch.
    Handles exceptions gracefully — never crashes.
    """

    def __init__(
        self,
        redis_client,
        signal_auditor: "SignalAuditor",
        trade_auditor: "TradeAuditor",
    ) -> None:
        self._redis = redis_client
        self._signal_auditor = signal_auditor
        self._trade_auditor = trade_auditor
        self._running = False

    async def run(self) -> None:
        """Blocking coroutine — runs until cancelled."""
        self._running = True
        logger.info("AuditConsumer starting — listening on %s", _QUEUE_KEY)

        while self._running:
            try:
                await self._consume_one()
            except asyncio.CancelledError:
                logger.info("AuditConsumer cancelled")
                break
            except Exception as exc:
                logger.error("AuditConsumer unexpected error: %s", exc)
                await asyncio.sleep(1)

    async def _consume_one(self) -> None:
        loop = asyncio.get_running_loop()

        # BLPOP with 5s timeout — runs in thread pool to avoid blocking
        result = await loop.run_in_executor(
            None,
            lambda: self._redis.blpop(_QUEUE_KEY, timeout=5),
        )

        if result is None:
            return  # timeout — loop again

        _key, raw = result
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("AuditConsumer: invalid JSON: %s | raw=%s", exc, raw[:200])
            return

        event_type = data.get("type", "signal_snapshot")
        logger.debug("AuditConsumer: dispatching event type=%s", event_type)

        try:
            if event_type == "signal_snapshot":
                await self._signal_auditor.process(data)
            elif event_type == "trade_opened":
                await self._trade_auditor.on_trade_opened(data)
            elif event_type == "trade_closed":
                await self._trade_auditor.on_trade_closed(data)
            else:
                logger.warning("AuditConsumer: unknown event type: %s", event_type)
        except Exception as exc:
            logger.error(
                "AuditConsumer: dispatch error for type=%s: %s", event_type, exc
            )

    def stop(self) -> None:
        self._running = False
