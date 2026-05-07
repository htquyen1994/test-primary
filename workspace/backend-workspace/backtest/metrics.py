"""
Performance Metrics
====================
Computes all required metrics after a backtest run.

Metrics:
  - Win rate (%)
  - Profit factor
  - Max drawdown (%)
  - Sharpe Ratio (annualized, daily returns, sqrt(365))
  - Recovery Factor

Satisfies: Requirements 9.1–9.6, 11.1, 11.2
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List

import numpy as np

from backtest.models import TradeResult

logger = logging.getLogger(__name__)

MIN_TRADES_FOR_STATS = 30  # Req 11.6


def compute_metrics(trades: List[TradeResult]) -> dict:
    """
    Compute all performance metrics from a list of closed trades.

    Args:
        trades: List of TradeResult objects (all closed)

    Returns:
        Dict with all metrics. Flags is_statistically_insufficient if < 30 trades.

    Satisfies: Requirements 9.1–9.6
    """
    n = len(trades)
    is_insufficient = n < MIN_TRADES_FOR_STATS

    if n == 0:
        return _empty_metrics(is_insufficient)

    # Win rate (Req 9.2)
    wins = [t for t in trades if t.result == "win"]
    win_rate = len(wins) / n  # [0.0, 1.0]

    # Profit factor (Req 9.1)
    gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Equity curve for drawdown and Sharpe
    equity_curve = _build_equity_curve(trades)

    # Max drawdown (Req 9.4)
    max_drawdown = _compute_max_drawdown(equity_curve)

    # Sharpe Ratio (Req 9.3): daily returns, annualized by sqrt(365)
    sharpe = _compute_sharpe(equity_curve)

    # Recovery Factor (Req 9.5)
    net_profit = sum(t.net_pnl for t in trades)
    recovery_factor = net_profit / abs(max_drawdown) if max_drawdown != 0 else float("inf")

    return {
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown": round(max_drawdown, 4),
        "sharpe_ratio": round(sharpe, 4),
        "recovery_factor": round(recovery_factor, 4),
        "total_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len([t for t in trades if t.result == "loss"]),
        "net_profit": round(net_profit, 4),
        "is_statistically_insufficient": is_insufficient,
    }


def write_result_record(
    metrics: dict,
    strategy_name: str,
    asset: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    config_snapshot: dict,
    log_dir: str = "logs/backtest/",
    is_walk_forward: bool = False,
    wf_window_index: int = None,
    is_in_sample: bool = None,
) -> str:
    """
    Write a structured result record to logs/backtest/.

    Satisfies: Requirements 9.6, 11.1, 11.2
    """
    os.makedirs(log_dir, exist_ok=True)
    run_id = str(uuid.uuid4())
    record = {
        "run_id": run_id,
        "strategy_name": strategy_name,
        "asset": asset,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "is_walk_forward": is_walk_forward,
        "wf_window_index": wf_window_index,
        "is_in_sample": is_in_sample,
        "config_snapshot": config_snapshot,
        **metrics,
    }
    path = os.path.join(log_dir, f"{run_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    logger.info("Backtest result written: %s", path)
    return run_id


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _empty_metrics(is_insufficient: bool) -> dict:
    return {
        "win_rate": 0.0, "profit_factor": 0.0, "max_drawdown": 0.0,
        "sharpe_ratio": 0.0, "recovery_factor": 0.0,
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
        "net_profit": 0.0, "is_statistically_insufficient": is_insufficient,
    }


def _build_equity_curve(trades: List[TradeResult]) -> np.ndarray:
    """Build cumulative equity curve from trade PnL."""
    pnls = np.array([t.net_pnl for t in trades])
    return np.cumsum(pnls)


def _compute_max_drawdown(equity_curve: np.ndarray) -> float:
    """
    Maximum percentage decline from any equity peak to subsequent trough.
    Returns negative value (e.g. -0.15 for 15% drawdown).

    Satisfies: Requirement 9.4
    """
    if len(equity_curve) == 0:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (val - peak) / abs(peak) if peak != 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _compute_sharpe(equity_curve: np.ndarray) -> float:
    """
    Sharpe Ratio = mean(daily_returns) / std(daily_returns) × sqrt(365).

    Satisfies: Requirement 9.3
    """
    if len(equity_curve) < 2:
        return 0.0
    daily_returns = np.diff(equity_curve)
    std = np.std(daily_returns, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(daily_returns) / std * np.sqrt(365))
