"""
Threshold Analyzer
===================
Sweeps the alert threshold from MIN to MAX and computes per-threshold statistics.

Key metrics at each threshold T:
  n_alerts   — signals with final_score >= T
  precision  — P(WIN | score >= T)  = win_rate at threshold
  recall     — P(score >= T | WIN)  = coverage of true winners
  f1         — harmonic mean of precision × recall
  ev         — Expected Value per trade = precision × avg_rr - (1-precision) × 1.0
  ev_ci_low  — bootstrap CI low (5th percentile)
  ev_ci_high — bootstrap CI high (95th percentile)

Optimal threshold T* = argmax(EV) subject to n_alerts >= MIN_SAMPLE_AT_T.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Minimum number of signals at a threshold to be considered valid
MIN_ALERTS_AT_THRESHOLD = 5
BOOTSTRAP_N = 1000
CI_ALPHA = 0.90   # 90% CI


@dataclass
class ThresholdStats:
    threshold: int
    n_total: int        # total signals at or above this threshold
    n_win: int
    n_loss: int
    precision: float    # win rate
    recall: float       # coverage of all wins
    f1: float
    ev: float           # expected value per trade (units of 1R)
    ev_ci_low: float
    ev_ci_high: float
    avg_rr: float       # average R:R of winning trades at this threshold

    @property
    def is_valid(self) -> bool:
        return self.n_total >= MIN_ALERTS_AT_THRESHOLD


@dataclass
class ThresholdAnalysis:
    curve: List[ThresholdStats]
    current_threshold: int
    optimal_threshold: int
    current_stats: Optional[ThresholdStats]
    optimal_stats: Optional[ThresholdStats]
    total_labeled: int
    total_win: int
    total_loss: int
    win_rate_overall: float
    # Per-score-bucket breakdown
    buckets: dict = field(default_factory=dict)


class ThresholdAnalyzer:
    """
    Computes precision-recall-EV curve across a range of thresholds.
    """

    def __init__(
        self,
        t_min: int = 50,
        t_max: int = 95,
        rr_win: Optional[float] = None,    # override avg R:R for EV calc
    ):
        self.t_min = t_min
        self.t_max = t_max
        self._rr_override = rr_win

    def analyze(self, df: pd.DataFrame, current_threshold: int = 75) -> ThresholdAnalysis:
        """
        Args:
            df: labeled DataFrame (WIN/LOSS rows only, from OutcomeLoader.to_labeled)
            current_threshold: current production alert threshold
        Returns:
            ThresholdAnalysis with full curve
        """
        if df.empty or "outcome" not in df.columns or "final_score" not in df.columns:
            logger.warning("ThresholdAnalyzer: empty or invalid DataFrame")
            return ThresholdAnalysis(
                curve=[], current_threshold=current_threshold,
                optimal_threshold=current_threshold,
                current_stats=None, optimal_stats=None,
                total_labeled=0, total_win=0, total_loss=0, win_rate_overall=0.0,
            )

        y      = (df["outcome"] == "WIN").astype(int).values
        scores = df["final_score"].astype(int).values
        rr_arr = df["rr_ratio"].astype(float).values if "rr_ratio" in df.columns else np.ones(len(y)) * 2.0

        total_win  = int(y.sum())
        total_loss = len(y) - total_win

        curve: List[ThresholdStats] = []
        for t in range(self.t_min, self.t_max + 1):
            mask = scores >= t
            stats = self._compute_stats(y, scores, rr_arr, mask, t, total_win)
            curve.append(stats)

        # Find optimal threshold (max EV among valid thresholds)
        valid = [s for s in curve if s.is_valid]
        optimal = max(valid, key=lambda s: s.ev) if valid else None
        optimal_t = optimal.threshold if optimal else current_threshold

        current_stats = next((s for s in curve if s.threshold == current_threshold), None)

        # Score bucket analysis
        buckets = self._bucket_analysis(y, scores, rr_arr)

        return ThresholdAnalysis(
            curve=curve,
            current_threshold=current_threshold,
            optimal_threshold=optimal_t,
            current_stats=current_stats,
            optimal_stats=optimal,
            total_labeled=len(df),
            total_win=total_win,
            total_loss=total_loss,
            win_rate_overall=float(total_win / len(df)) if len(df) > 0 else 0.0,
            buckets=buckets,
        )

    # ── Internal ───────────────────────────────────────────────────────────────

    def _compute_stats(
        self, y: np.ndarray, scores: np.ndarray, rr_arr: np.ndarray,
        mask: np.ndarray, threshold: int, total_win: int,
    ) -> ThresholdStats:
        n = int(mask.sum())
        if n == 0:
            return ThresholdStats(
                threshold=threshold, n_total=0, n_win=0, n_loss=0,
                precision=0.0, recall=0.0, f1=0.0, ev=0.0,
                ev_ci_low=0.0, ev_ci_high=0.0, avg_rr=2.0,
            )

        y_at = y[mask]
        rr_at = rr_arr[mask]
        n_win = int(y_at.sum())
        n_loss = n - n_win

        precision = n_win / n
        recall    = n_win / total_win if total_win > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Avg R:R of winning trades (clamp NaN)
        rr_wins = rr_at[y_at == 1]
        avg_rr = float(np.nanmean(rr_wins)) if len(rr_wins) > 0 else (self._rr_override or 2.0)
        if self._rr_override:
            avg_rr = self._rr_override

        ev = precision * avg_rr - (1.0 - precision) * 1.0

        # Bootstrap CI on EV
        ev_samples = self._bootstrap_ev(y_at, rr_at, avg_rr)
        ci_lo = float(np.percentile(ev_samples, (1 - CI_ALPHA) / 2 * 100))
        ci_hi = float(np.percentile(ev_samples, (1 - (1 - CI_ALPHA) / 2) * 100))

        return ThresholdStats(
            threshold=threshold, n_total=n, n_win=n_win, n_loss=n_loss,
            precision=round(precision, 4), recall=round(recall, 4),
            f1=round(f1, 4), ev=round(ev, 4),
            ev_ci_low=round(ci_lo, 4), ev_ci_high=round(ci_hi, 4),
            avg_rr=round(avg_rr, 2),
        )

    @staticmethod
    def _bootstrap_ev(y: np.ndarray, rr: np.ndarray, avg_rr: float) -> np.ndarray:
        n = len(y)
        if n < 3:
            return np.array([0.0] * BOOTSTRAP_N)
        evs = []
        rng = np.random.default_rng(42)
        for _ in range(BOOTSTRAP_N):
            idx = rng.integers(0, n, size=n)
            yb = y[idx]; rb = rr[idx]
            p = yb.mean()
            rr_w = rb[yb == 1]
            avg_rr_b = float(np.nanmean(rr_w)) if len(rr_w) > 0 else avg_rr
            evs.append(p * avg_rr_b - (1 - p) * 1.0)
        return np.array(evs)

    @staticmethod
    def _bucket_analysis(
        y: np.ndarray, scores: np.ndarray, rr_arr: np.ndarray,
    ) -> dict:
        buckets = {}
        for lo, hi in [(55,59),(60,64),(65,69),(70,74),(75,79),(80,84),(85,89),(90,100)]:
            mask = (scores >= lo) & (scores <= hi)
            n = mask.sum()
            if n == 0:
                continue
            y_b = y[mask]
            rr_b = rr_arr[mask]
            wins = int(y_b.sum())
            avg_rr = float(np.nanmean(rr_b[y_b == 1])) if wins > 0 else 2.0
            ev = (wins / n) * avg_rr - (1 - wins / n) * 1.0
            buckets[f"{lo}-{hi}"] = {
                "n": int(n), "wins": wins, "losses": int(n - wins),
                "win_rate": round(float(wins / n), 3),
                "avg_rr": round(avg_rr, 2),
                "ev": round(ev, 3),
            }
        return buckets
