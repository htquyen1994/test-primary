"""
Benchmark Table Generator
==========================
Reads all backtest result records and produces a comparison table
showing all strategies × timeframes with all performance metrics.

Satisfies: Requirements 17.5, 17.6
"""

from __future__ import annotations

import json
import logging
import os
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

INSUFFICIENT_MARKER = "⚠ insufficient"


def generate_benchmark_table(log_dir: str = "logs/backtest/") -> pd.DataFrame:
    """
    Read all backtest result records and produce a Benchmark_Table.

    Rows:    strategy × timeframe
    Columns: win_rate, profit_factor, max_drawdown, sharpe_ratio,
             recovery_factor, total_trades, is_statistically_insufficient

    Rows with < 30 trades are marked as statistically insufficient.

    Satisfies: Requirements 17.5, 17.6
    """
    if not os.path.exists(log_dir):
        logger.warning("Log directory not found: %s", log_dir)
        return pd.DataFrame()

    records = []
    for fname in os.listdir(log_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(log_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
            records.append(record)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read %s: %s", path, exc)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Select and rename columns
    cols = [
        "strategy_name", "asset", "timeframe",
        "win_rate", "profit_factor", "max_drawdown",
        "sharpe_ratio", "recovery_factor",
        "total_trades", "is_statistically_insufficient",
    ]
    available = [c for c in cols if c in df.columns]
    df = df[available].copy()

    # Mark insufficient rows
    if "is_statistically_insufficient" in df.columns:
        df["note"] = df["is_statistically_insufficient"].apply(
            lambda x: INSUFFICIENT_MARKER if x else ""
        )

    # Sort by strategy + asset + timeframe
    sort_cols = [c for c in ["strategy_name", "asset", "timeframe"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    return df
