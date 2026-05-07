"""
Trade Journal Writer
=====================
Records entry/exit fills and computes final PnL in the database.

Satisfies: Requirements 19.5, 19.6, 19.10
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def record_entry(
    signal_card: dict,
    fill_price: float,
    order_id: str,
    position_size_usd: float,
    fee_rate: float,
    db_session,
) -> str:
    """
    Insert a trade_journal row after entry fill.

    Satisfies: Requirements 19.5, 19.6
    """
    from db.models import TradeJournal

    trade_id = str(uuid.uuid4())
    entry_price = signal_card["entry_price"]
    slippage = fill_price - entry_price
    fee_entry = fill_price * fee_rate

    row = TradeJournal(
        trade_id=trade_id,
        strategy_name=signal_card.get("strategy_name", "unknown"),
        asset=signal_card["asset"],
        timeframe=signal_card.get("timeframe", "15m"),
        direction=signal_card["direction"],
        entry_timestamp=datetime.now(timezone.utc),
        entry_price=entry_price,
        actual_entry_price=fill_price,
        stop_loss=signal_card["stop_loss"],
        take_profit_1=signal_card["take_profit_1"],
        take_profit_2=signal_card.get("take_profit_2"),
        position_size_usd=position_size_usd,
        slippage_entry=slippage,
        fee_entry=fee_entry,
        signal_score=signal_card.get("final_score", 0),
        exchange_order_id=order_id,
        is_testnet=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()

    logger.info(
        "Trade entry recorded: %s %s fill=%.4f slip=%.4f",
        signal_card["asset"], signal_card["direction"], fill_price, slippage,
    )
    return trade_id


def record_exit(
    trade_id: str,
    exit_price: float,
    exit_order_id: str,
    fee_rate: float,
    funding_paid: float,
    db_session,
) -> None:
    """
    Update trade_journal with exit fill, compute gross/net PnL and result.

    Satisfies: Requirements 19.5, 19.6, 19.10
    """
    from db.models import TradeJournal
    from sqlalchemy import select

    row = db_session.execute(
        select(TradeJournal).where(TradeJournal.trade_id == trade_id)
    ).scalar_one_or_none()

    if row is None:
        logger.error("Trade %s not found for exit recording", trade_id)
        return

    actual_entry = row.actual_entry_price or row.entry_price
    fee_exit = exit_price * fee_rate
    slippage_exit = exit_price - (row.take_profit_1 if exit_price >= row.take_profit_1 else row.stop_loss)

    # Gross PnL
    if row.direction == "long":
        gross_pnl = (exit_price - actual_entry) * (row.position_size_usd / actual_entry)
    else:
        gross_pnl = (actual_entry - exit_price) * (row.position_size_usd / actual_entry)

    # Net PnL = gross - fees - slippage - funding
    net_pnl = gross_pnl - row.fee_entry - fee_exit - funding_paid

    result = "win" if net_pnl > 0 else "loss" if net_pnl < 0 else "be"

    row.exit_timestamp = datetime.now(timezone.utc)
    row.exit_price = exit_price
    row.actual_exit_price = exit_price
    row.slippage_exit = slippage_exit
    row.fee_exit = fee_exit
    row.funding_paid = funding_paid
    row.gross_pnl = round(gross_pnl, 8)
    row.net_pnl = round(net_pnl, 8)
    row.result = result
    row.updated_at = datetime.now(timezone.utc)

    db_session.commit()

    logger.info(
        "Trade exit recorded: %s result=%s net_pnl=%.4f",
        trade_id, result, net_pnl,
    )
