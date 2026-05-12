"""
Signal Log Writer
==================
Writes Signal_Log entries to the database for every generated signal.

Satisfies: Requirements 17.1, 17.2, 17.3, 17.7
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from strategies.signal import Signal

logger = logging.getLogger(__name__)


def write_signal_log(signal: Signal, db_session) -> str:
    """
    Insert a Signal_Log row for every generated signal.
    Called regardless of classification (ALERT/WATCH/IGNORE).

    Satisfies: Requirements 17.1, 17.2, 17.7
    """
    from db.models import SignalLog

    log_id = str(uuid.uuid4())
    row = SignalLog(
        log_id=log_id,
        timestamp=signal.candle_timestamp,
        asset=signal.asset,
        timeframe=signal.timeframe,
        strategy_name=signal.strategy_name,
        direction=signal.direction,
        candle_index=signal.candle_index,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit_1=signal.take_profit_1,
        take_profit_2=signal.take_profit_2,
        raw_score=signal.raw_score,
        final_score=signal.final_score,
        score_order_flow=signal.score_breakdown.order_flow,
        score_smc=signal.score_breakdown.smc,
        score_vsa=signal.score_breakdown.vsa,
        score_context=signal.score_breakdown.context,
        score_bonus=signal.score_breakdown.bonus,
        regime=signal.regime,
        regime_multiplier=signal.regime_multiplier,
        funding_rate=signal.funding_rate,
        portfolio_heat=signal.portfolio_heat,
        correlated_group_risk=signal.correlated_group_risk,
        classification=signal.classification,
        user_action=signal.user_action,
        skip_reason=signal.skip_reason,
        expiry_price=signal.expiry_price,
        expires_at_candle=signal.expires_at_candle,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()
    logger.debug("Signal_Log written: %s %s score=%d", signal.asset, signal.direction, signal.final_score)
    return log_id


def update_user_action(
    log_id: str,
    action: str,
    skip_reason: Optional[str],
    db_session,
) -> None:
    """
    Update user_action and skip_reason after user confirms or skips.

    Satisfies: Requirements 17.3
    """
    from db.models import SignalLog
    from sqlalchemy import update

    db_session.execute(
        update(SignalLog)
        .where(SignalLog.log_id == log_id)
        .values(user_action=action, skip_reason=skip_reason)
    )
    db_session.commit()
    logger.debug("Signal_Log updated: %s action=%s", log_id, action)
