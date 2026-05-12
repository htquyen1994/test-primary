"""
PositionTracker — SL/TP check per candle OHLCV.
Called by CandleFeed on every candle_close event.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import MockPosition
from exchange.order_manager import OrderManager

logger = logging.getLogger(__name__)


class PositionTracker:
    """
    Checks open positions for SL/TP triggers using candle high/low.
    On fill: closes position, applies PnL, records account history,
    and publishes to mock_exchange:fills channel.
    """

    def __init__(
        self,
        order_manager: OrderManager,
        db_factory,
        redis_client,
    ) -> None:
        self._om = order_manager
        self._db_factory = db_factory
        self._redis = redis_client

    async def check_positions_for_symbol(
        self,
        symbol: str,
        timeframe: str,
        candle_high: float,
        candle_low: float,
        candle_close: float,
    ) -> None:
        """
        Check all open positions for symbol against candle high/low.
        Priority: SL check first, then TP2, then TP1.
        """
        db: Session = self._db_factory()
        try:
            positions = self._om.get_open_positions(db, symbol)
            for pos in positions:
                await self._check_position(
                    db, pos, candle_high, candle_low, candle_close, timeframe
                )
        except Exception as exc:
            logger.error("Error checking positions for %s: %s", symbol, exc)
        finally:
            db.close()

    async def _check_position(
        self,
        db: Session,
        pos: MockPosition,
        high: float,
        low: float,
        close: float,
        timeframe: str,
    ) -> None:
        direction = pos.direction
        fill_price = None
        exit_reason = None

        if direction == "long":
            # SL check: candle low touched or crossed SL
            if low <= pos.stop_loss:
                fill_price = pos.stop_loss
                exit_reason = "SL_HIT"
            # TP2 check (higher priority than TP1)
            elif pos.take_profit_2 and high >= pos.take_profit_2:
                fill_price = pos.take_profit_2
                exit_reason = "TP2_HIT"
            # TP1 check
            elif high >= pos.take_profit_1:
                fill_price = pos.take_profit_1
                exit_reason = "TP1_HIT"
        else:  # short
            # SL check: candle high touched or crossed SL
            if high >= pos.stop_loss:
                fill_price = pos.stop_loss
                exit_reason = "SL_HIT"
            # TP2 check
            elif pos.take_profit_2 and low <= pos.take_profit_2:
                fill_price = pos.take_profit_2
                exit_reason = "TP2_HIT"
            # TP1 check
            elif low <= pos.take_profit_1:
                fill_price = pos.take_profit_1
                exit_reason = "TP1_HIT"

        if fill_price and exit_reason:
            await self._close_position(
                db, pos, fill_price, exit_reason, timeframe
            )

    async def _close_position(
        self,
        db: Session,
        pos: MockPosition,
        exit_price: float,
        exit_reason: str,
        timeframe: str,
    ) -> None:
        closed_at_iso = datetime.now(timezone.utc).isoformat()

        # Calculate PnL
        pnl_data = self._om.calculate_pnl(
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            amount=pos.amount,
            leverage=pos.leverage,
            opened_at_iso=pos.opened_at,
            closed_at_iso=closed_at_iso,
            funding_rate=pos.funding_rate_at_entry,
        )

        # Close the position in DB
        pos = self._om.close_position(db, pos, exit_price, exit_reason)

        # Apply PnL to account
        fee_total = pnl_data["fee_entry"] + pnl_data["fee_exit"]
        self._om.apply_pnl(
            db=db,
            net_pnl=pnl_data["net_pnl"],
            fee_total=fee_total,
            position_id=pos.id,
            exit_reason=exit_reason,
        )

        logger.info(
            "Position closed: id=%s symbol=%s reason=%s exit=%.4f net_pnl=%.4f",
            pos.id, pos.symbol, exit_reason, exit_price, pnl_data["net_pnl"],
        )

        # Publish fill event to Redis
        fill_event = {
            "position_id": pos.id,
            "symbol": pos.symbol,
            "direction": pos.direction,
            "exit_reason": exit_reason,
            "exit_price": exit_price,
            "net_pnl": pnl_data["net_pnl"],
            "pnl_pct": pnl_data["pnl_pct"],
            "gross_pnl": pnl_data["gross_pnl"],
            "hold_hours": pnl_data["hold_hours"],
            "signal_id": pos.signal_id,
            "closed_at": closed_at_iso,
            "timeframe": timeframe,
        }

        try:
            self._redis.publish("mock_exchange:fills", json.dumps(fill_event))
        except Exception as exc:
            logger.warning("Failed to publish fill event: %s", exc)

        # Notify TradeAuditor via Redis as well
        try:
            trade_closed_event = {
                "type": "trade_closed",
                "position_id": pos.id,
                "signal_id": pos.signal_id,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "amount": pos.amount,
                "leverage": pos.leverage,
                "opened_at": pos.opened_at,
                "closed_at": closed_at_iso,
                "net_pnl": pnl_data["net_pnl"],
                "gross_pnl": pnl_data["gross_pnl"],
                "pnl_pct": pnl_data["pnl_pct"],
                "hold_hours": pnl_data["hold_hours"],
            }
            self._redis.rpush("audit:pending_snapshots", json.dumps(trade_closed_event))
        except Exception as exc:
            logger.warning("Failed to push trade_closed audit event: %s", exc)
