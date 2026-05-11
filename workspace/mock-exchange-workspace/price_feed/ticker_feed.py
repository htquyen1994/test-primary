"""
TickerFeed — polls ccxt ticker every N seconds for open positions.
Broadcasts unrealized PnL via WebSocket. Does NOT trigger fills.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class TickerFeed:
    """
    Async background task that:
    1. Polls ccxt ticker for every symbol with an open position
    2. Broadcasts price + unrealized PnL to WebSocket clients
    """

    def __init__(
        self,
        db_factory,
        exchange_id: str = "binance",
        poll_interval: float = 10.0,
        ws_manager=None,
        redis_client=None,
    ) -> None:
        self._db_factory = db_factory
        self._exchange_id = exchange_id
        self._poll_interval = poll_interval
        self._ws_manager = ws_manager
        self._redis = redis_client
        self._running = False

    async def run(self) -> None:
        """Blocking coroutine — polls until cancelled."""
        self._running = True
        logger.info(
            "TickerFeed starting — poll interval: %ss", self._poll_interval
        )
        while self._running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                logger.info("TickerFeed cancelled")
                break
            except Exception as exc:
                logger.error("TickerFeed error: %s", exc)
            await asyncio.sleep(self._poll_interval)

    async def _poll_once(self) -> None:
        from db.models import MockPosition
        from trading_core.exchange.client import get_exchange_client

        loop = asyncio.get_running_loop()
        db = self._db_factory()
        try:
            positions = (
                db.query(MockPosition)
                .filter(MockPosition.status == "OPEN")
                .all()
            )
        finally:
            db.close()

        if not positions:
            return

        # Deduplicate symbols
        symbols = list({p.symbol for p in positions})
        client = get_exchange_client(self._exchange_id)

        for symbol in symbols:
            try:
                ticker = await loop.run_in_executor(
                    None, lambda s=symbol: client.fetch_ticker(s)
                )
                current_price = float(ticker.get("last", ticker.get("close", 0.0)))
                if current_price <= 0:
                    continue

                # Build updates for all positions with this symbol
                updates = []
                for pos in positions:
                    if pos.symbol != symbol:
                        continue
                    if pos.direction == "long":
                        unrealized_pnl = (current_price - pos.entry_price) * pos.amount * pos.leverage
                    else:
                        unrealized_pnl = (pos.entry_price - current_price) * pos.amount * pos.leverage
                    entry_value = pos.entry_price * pos.amount
                    pnl_pct = (unrealized_pnl / entry_value * 100) if entry_value != 0 else 0.0

                    updates.append({
                        "position_id": pos.id,
                        "symbol": symbol,
                        "direction": pos.direction,
                        "current_price": current_price,
                        "unrealized_pnl": round(unrealized_pnl, 4),
                        "unrealized_pnl_pct": round(pnl_pct, 2),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })

                if updates and self._ws_manager:
                    for update in updates:
                        await self._ws_manager.broadcast_positions(json.dumps(update))

                # Publish to Redis pnl channel
                if updates and self._redis:
                    try:
                        self._redis.publish(
                            "mock_exchange:pnl",
                            json.dumps({"symbol": symbol, "updates": updates}),
                        )
                    except Exception as exc:
                        logger.debug("Failed to publish PnL to Redis: %s", exc)

            except Exception as exc:
                logger.warning("TickerFeed: failed to fetch ticker for %s: %s", symbol, exc)

    def stop(self) -> None:
        self._running = False
