"""
AI Feedback Loop — Underperformance Cluster Detection
======================================================
Reads backtest result records and identifies contiguous date ranges
where win rate < 45% or profit factor < 1.0.

Satisfies: Requirements 11.3–11.6
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

WIN_RATE_THRESHOLD = 0.45
PROFIT_FACTOR_THRESHOLD = 1.0


def find_underperformance_clusters(log_entries: List[dict]) -> List[dict]:
    """
    Identify contiguous date ranges where win rate < 45% or profit factor < 1.0.
    Excludes runs with < 30 trades (statistically insufficient).

    Args:
        log_entries: List of backtest result dicts (from logs/backtest/)

    Returns:
        List of cluster dicts with date range, strategy, asset, and suggestions

    Satisfies: Requirements 11.3, 11.4, 11.6
    """
    # Filter out statistically insufficient runs (Req 11.6)
    valid = [
        e for e in log_entries
        if not e.get("is_statistically_insufficient", True)
        and e.get("total_trades", 0) >= 30
    ]

    if not valid:
        return []

    # Group by strategy + asset
    groups: dict = {}
    for entry in valid:
        key = f"{entry.get('strategy_name', 'unknown')}_{entry.get('asset', 'unknown')}"
        groups.setdefault(key, []).append(entry)

    clusters = []
    for key, entries in groups.items():
        # Sort by start_date
        entries_sorted = sorted(entries, key=lambda e: e.get("start_date", ""))

        # Find contiguous underperforming windows
        cluster_start = None
        cluster_end = None
        cluster_entries = []

        for entry in entries_sorted:
            wr = entry.get("win_rate", 1.0)
            pf = entry.get("profit_factor", 1.0)
            is_underperforming = wr < WIN_RATE_THRESHOLD or pf < PROFIT_FACTOR_THRESHOLD

            if is_underperforming:
                if cluster_start is None:
                    cluster_start = entry.get("start_date")
                cluster_end = entry.get("end_date")
                cluster_entries.append(entry)
            else:
                if cluster_start is not None:
                    clusters.append(_build_cluster(
                        cluster_start, cluster_end, cluster_entries,
                    ))
                    cluster_start = None
                    cluster_end = None
                    cluster_entries = []

        # Close final cluster
        if cluster_start is not None:
            clusters.append(_build_cluster(
                cluster_start, cluster_end, cluster_entries,
            ))

    return clusters


def _build_cluster(start: str, end: str, entries: List[dict]) -> dict:
    """Build a structured cluster suggestion record."""
    strategy = entries[0].get("strategy_name", "unknown")
    asset = entries[0].get("asset", "unknown")
    avg_wr = sum(e.get("win_rate", 0) for e in entries) / len(entries)
    avg_pf = sum(e.get("profit_factor", 0) for e in entries) / len(entries)

    suggestions = []
    if avg_wr < WIN_RATE_THRESHOLD:
        suggestions.append(
            f"Win rate {avg_wr:.1%} below threshold — consider tightening entry conditions "
            f"(e.g. require stronger HTF bias alignment or higher score threshold)"
        )
    if avg_pf < PROFIT_FACTOR_THRESHOLD:
        suggestions.append(
            f"Profit factor {avg_pf:.2f} below 1.0 — consider widening TP or tightening SL "
            f"(e.g. use ATR-based SL instead of fixed percentage)"
        )

    return {
        "cluster_id": str(uuid.uuid4()),
        "strategy_name": strategy,
        "asset": asset,
        "start_date": start,
        "end_date": end,
        "window_count": len(entries),
        "avg_win_rate": round(avg_wr, 4),
        "avg_profit_factor": round(avg_pf, 4),
        "suggestions": suggestions,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_optimization_suggestions(
    clusters: List[dict],
    log_dir: str = "logs/optimization/",
) -> None:
    """
    Write optimization suggestion records to logs/optimization/.
    Stored separately from raw backtest results.

    Satisfies: Requirement 11.5
    """
    os.makedirs(log_dir, exist_ok=True)
    for cluster in clusters:
        path = os.path.join(log_dir, f"{cluster['cluster_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cluster, f, indent=2)
    logger.info("Wrote %d optimization suggestion(s) to %s", len(clusters), log_dir)
