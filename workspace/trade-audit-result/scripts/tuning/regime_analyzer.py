"""
Regime Analyzer
================
Computes win-rate and optimal threshold per regime.

Answers:
  - Which regime produces the best win rate?
  - Should CHOPPY signals be blocked entirely?
  - Are per-regime thresholds worth implementing?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_REGIME_SAMPLE = 5


@dataclass
class RegimeStats:
    regime: str
    n: int
    n_win: int
    n_loss: int
    win_rate: float
    avg_score: float
    median_score: float
    avg_mae: float    # avg max adverse excursion (%)
    avg_mfe: float    # avg max favorable excursion (%)
    recommendation: str  # "KEEP" | "RAISE_THRESHOLD" | "BLOCK" | "LOWER_THRESHOLD"

    @property
    def is_valid(self) -> bool:
        return self.n >= MIN_REGIME_SAMPLE


@dataclass
class RegimeAnalysis:
    regimes: Dict[str, RegimeStats]
    best_regime: str
    worst_regime: str
    block_candidates: List[str]   # regimes where win_rate < 40%


class RegimeAnalyzer:

    def analyze(self, df: pd.DataFrame) -> RegimeAnalysis:
        if df.empty or "regime" not in df.columns:
            return RegimeAnalysis(regimes={}, best_regime="", worst_regime="", block_candidates=[])

        results: Dict[str, RegimeStats] = {}
        for regime, grp in df.groupby("regime"):
            stats = self._compute(regime, grp)
            results[regime] = stats

        valid = {k: v for k, v in results.items() if v.is_valid}
        if not valid:
            return RegimeAnalysis(regimes=results, best_regime="", worst_regime="", block_candidates=[])

        best  = max(valid, key=lambda k: valid[k].win_rate)
        worst = min(valid, key=lambda k: valid[k].win_rate)
        blocks = [k for k, v in valid.items() if v.win_rate < 0.40]

        return RegimeAnalysis(regimes=results, best_regime=best, worst_regime=worst, block_candidates=blocks)

    @staticmethod
    def _compute(regime: str, grp: pd.DataFrame) -> RegimeStats:
        n = len(grp)
        n_win  = int((grp["outcome"] == "WIN").sum())
        n_loss = int((grp["outcome"] == "LOSS").sum())
        win_rate = n_win / (n_win + n_loss) if (n_win + n_loss) > 0 else 0.0

        avg_score    = float(grp["final_score"].mean())
        median_score = float(grp["final_score"].median())
        avg_mae = float(grp["mae_pct"].mean()) if "mae_pct" in grp.columns else 0.0
        avg_mfe = float(grp["mfe_pct"].mean()) if "mfe_pct" in grp.columns else 0.0

        # Recommendation heuristics
        if n < MIN_REGIME_SAMPLE:
            rec = "INSUFFICIENT_SAMPLE"
        elif win_rate < 0.35:
            rec = "BLOCK"
        elif win_rate < 0.48:
            rec = "RAISE_THRESHOLD"
        elif win_rate > 0.62:
            rec = "LOWER_THRESHOLD"
        else:
            rec = "KEEP"

        return RegimeStats(
            regime=regime, n=n, n_win=n_win, n_loss=n_loss,
            win_rate=round(win_rate, 3),
            avg_score=round(avg_score, 1),
            median_score=round(median_score, 1),
            avg_mae=round(avg_mae, 3),
            avg_mfe=round(avg_mfe, 3),
            recommendation=rec,
        )
