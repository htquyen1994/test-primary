"""
Weight Analyzer
================
Identifies which scoring modules actually predict trade outcomes.

Two analyses:

[A] Module Importance (read-only)
    For each module score (OF, SMC, VSA, CTX, Bonus):
      - Point-biserial correlation with binary outcome (1=WIN, 0=LOSS)
      - AUC-ROC using that module alone as a classifier
      - Cohen's d (effect size between WIN and LOSS groups)
      - Mann-Whitney U p-value (non-parametric significance test)

[B] Weight Optimization (coordinate descent)
    Starts from weights = (1.0, 1.0, 1.0, 1.0, 1.0)
    For each module in turn:
      - Sweeps weight from WEIGHT_MIN to WEIGHT_MAX
      - Evaluates AUC-ROC of the re-scored signals
      - Picks the weight that maximizes AUC-ROC
    Repeats until AUC improvement < CONVERGENCE_TOL or max iterations reached.

Re-scoring formula (matches scorer.py logic):
    raw_adj = Σ score_i × w_i
    max_adj = 35×w_of + 30×w_smc + 30×w_vsa + 15×w_ctx + 15×w_bonus
    final   = round(raw_adj × regime_mult / max_adj × 100)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MODULE_CAPS = {"of": 35.0, "smc": 30.0, "vsa": 30.0, "ctx": 15.0, "bonus": 15.0}
MODULE_COLS = {
    "of":    "score_order_flow",
    "smc":   "score_smc",
    "vsa":   "score_vsa",
    "ctx":   "score_context",
    "bonus": "score_bonus",
}

WEIGHT_MIN   = 0.25
WEIGHT_MAX   = 3.00
WEIGHT_STEPS = 23   # 0.25 → 3.0 in 0.125 steps
COORD_MAX_ITER = 10
CONVERGENCE_TOL = 0.002   # stop when AUC improvement < 0.2%
MIN_SAMPLE_FOR_OPTIMIZATION = 15


@dataclass
class ModuleStats:
    name: str
    col: str
    correlation: float       # point-biserial r with outcome
    auc_roc: float           # AUC when used as sole classifier
    cohens_d: float          # standardised effect size
    p_value: float           # Mann-Whitney U p-value
    mean_win: float          # avg score in WIN signals
    mean_loss: float         # avg score in LOSS signals
    importance_rank: int = 0 # set by WeightAnalyzer after sorting

    @property
    def is_significant(self) -> bool:
        return self.p_value < 0.05 and abs(self.correlation) > 0.1

    @property
    def direction(self) -> str:
        """Is a higher score positively or negatively correlated with WIN?"""
        return "positive" if self.correlation > 0 else "negative"


@dataclass
class WeightOptResult:
    weights: Dict[str, float]   # optimized weights {of, smc, vsa, ctx, bonus}
    auc_baseline: float         # AUC with all weights = 1.0
    auc_optimized: float        # AUC with optimized weights
    auc_improvement: float      # absolute AUC gain
    iterations: int
    converged: bool
    n_used: int                 # sample size used for optimization


@dataclass
class WeightAnalysis:
    module_stats: List[ModuleStats]
    optimization: WeightOptResult
    insufficient_sample: bool = False
    sample_n: int = 0


class WeightAnalyzer:
    """
    Analyzes module predictiveness and finds optimal weight multipliers.
    """

    def analyze(self, df: pd.DataFrame) -> WeightAnalysis:
        """
        Args:
            df: labeled DataFrame (WIN/LOSS rows, from OutcomeLoader.to_labeled)
        """
        if df.empty:
            return WeightAnalysis(
                module_stats=[], insufficient_sample=True, sample_n=0,
                optimization=WeightOptResult(
                    weights={k: 1.0 for k in MODULE_CAPS},
                    auc_baseline=0.5, auc_optimized=0.5,
                    auc_improvement=0.0, iterations=0, converged=False, n_used=0,
                ),
            )

        y = (df["outcome"] == "WIN").astype(float).values
        n = len(y)
        insufficient = n < MIN_SAMPLE_FOR_OPTIMIZATION

        # [A] Module importance
        module_stats = []
        for key, col in MODULE_COLS.items():
            if col not in df.columns:
                continue
            x = df[col].astype(float).fillna(0).values
            stats = self._module_stats(key, col, x, y)
            module_stats.append(stats)

        # Rank by |correlation|
        module_stats.sort(key=lambda s: abs(s.correlation), reverse=True)
        for rank, s in enumerate(module_stats, 1):
            s.importance_rank = rank

        # [B] Weight optimization
        if insufficient:
            logger.info("WeightAnalyzer: sample N=%d < %d — returning default weights", n, MIN_SAMPLE_FOR_OPTIMIZATION)
            opt = WeightOptResult(
                weights={k: 1.0 for k in MODULE_CAPS},
                auc_baseline=self._compute_auc(self._rescore(df, {k: 1.0 for k in MODULE_CAPS}), y),
                auc_optimized=0.5,
                auc_improvement=0.0, iterations=0, converged=False, n_used=n,
            )
        else:
            opt = self._optimize_weights(df, y)

        return WeightAnalysis(
            module_stats=module_stats,
            optimization=opt,
            insufficient_sample=insufficient,
            sample_n=n,
        )

    # ── Module stats ──────────────────────────────────────────────────────────

    @staticmethod
    def _module_stats(key: str, col: str, x: np.ndarray, y: np.ndarray) -> ModuleStats:
        # Point-biserial correlation = Pearson r between binary y and continuous x
        if x.std() == 0 or y.std() == 0:
            corr = 0.0
        else:
            corr = float(np.corrcoef(x, y)[0, 1])
            corr = 0.0 if np.isnan(corr) else corr

        # AUC-ROC (using score as threshold sweep)
        auc = WeightAnalyzer._auc_from_scores(x, y)

        # Cohen's d
        g0 = x[y == 0]; g1 = x[y == 1]
        if len(g0) < 2 or len(g1) < 2:
            cohens_d = 0.0
        else:
            s0, s1 = g0.std(ddof=1), g1.std(ddof=1)
            pooled_var = ((len(g0)-1)*s0**2 + (len(g1)-1)*s1**2) / (len(g0)+len(g1)-2)
            pooled_std = float(np.sqrt(pooled_var))
            cohens_d = float((g1.mean() - g0.mean()) / pooled_std) if pooled_std > 0 else 0.0

        # Approximate p-value via normal approximation of Mann-Whitney U statistic
        p_mw = WeightAnalyzer._mw_pvalue(g1, g0)

        return ModuleStats(
            name=key, col=col,
            correlation=round(corr, 4),
            auc_roc=round(auc, 4),
            cohens_d=round(cohens_d, 4),
            p_value=round(p_mw, 4),
            mean_win=round(float(g1.mean()) if len(g1) > 0 else 0.0, 2),
            mean_loss=round(float(g0.mean()) if len(g0) > 0 else 0.0, 2),
        )

    @staticmethod
    def _mw_pvalue(group1: np.ndarray, group2: np.ndarray) -> float:
        """
        One-sided Mann-Whitney U p-value: P(group1 > group2).
        Uses normal approximation — valid for n1, n2 >= 5.
        Returns 1.0 if insufficient data.
        """
        n1, n2 = len(group1), len(group2)
        if n1 < 5 or n2 < 5:
            return 1.0
        # Rank-sum approach
        combined = np.concatenate([group1, group2])
        ranks = combined.argsort().argsort().astype(float) + 1.0
        # Handle ties: assign average ranks
        _, inv, counts = np.unique(combined, return_inverse=True, return_counts=True)
        tie_avg = np.zeros(len(combined))
        start = 0
        for cnt in counts:
            avg = (start + 1 + start + cnt) / 2.0
            tie_avg[start:start+cnt] = avg
            start += cnt
        # Re-index
        sorted_idx = combined.argsort()
        ranks_final = np.empty(len(combined))
        ranks_final[sorted_idx] = tie_avg

        R1 = ranks_final[:n1].sum()
        U1 = R1 - n1*(n1+1)/2.0
        # Mean and variance of U under H0
        mu_U = n1 * n2 / 2.0
        # Tie correction
        N = n1 + n2
        tie_correction = sum((c**3 - c) for c in counts if c > 1)
        var_U = (n1 * n2 / 12.0) * (N + 1 - tie_correction / (N*(N-1))) if N > 2 else 1.0
        if var_U <= 0:
            return 1.0
        z = (U1 - mu_U) / float(np.sqrt(var_U))
        # One-sided p-value via standard normal CDF approximation
        # Abramowitz & Stegun rational approximation
        p = WeightAnalyzer._norm_sf(z)
        return float(np.clip(p, 1e-6, 1.0))

    @staticmethod
    def _norm_sf(z: float) -> float:
        """P(Z > z) for standard normal Z — rational approximation."""
        # Use symmetry: sf(z) = cdf(-z)
        x = -z
        # Abramowitz & Stegun 26.2.17
        t = 1.0 / (1.0 + 0.2316419 * abs(x))
        poly = t * (0.319381530
                    + t * (-0.356563782
                    + t * (1.781477937
                    + t * (-1.821255978
                    + t * 1.330274429))))
        pdf = np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)
        cdf = 1.0 - pdf * poly
        return float(1.0 - cdf) if x >= 0 else float(cdf)

    @staticmethod
    def _auc_from_scores(scores: np.ndarray, y: np.ndarray) -> float:
        """Compute AUC-ROC using scores as continuous predictor."""
        thresholds = np.unique(scores)[::-1]
        tps, fps = [], []
        total_pos = y.sum()
        total_neg = len(y) - total_pos
        if total_pos == 0 or total_neg == 0:
            return 0.5
        for t in thresholds:
            pred = (scores >= t).astype(int)
            tps.append((pred * y).sum() / total_pos)
            fps.append((pred * (1 - y)).sum() / total_neg)
        tps = np.array([0.0] + tps + [1.0])
        fps = np.array([0.0] + fps + [1.0])
        return float(np.trapz(tps, fps))

    # ── Weight optimization ───────────────────────────────────────────────────

    def _optimize_weights(self, df: pd.DataFrame, y: np.ndarray) -> WeightOptResult:
        weights = {k: 1.0 for k in MODULE_CAPS}
        w_grid = np.linspace(WEIGHT_MIN, WEIGHT_MAX, WEIGHT_STEPS)

        baseline_scores = self._rescore(df, weights)
        auc_baseline = self._compute_auc(baseline_scores, y)
        auc_current  = auc_baseline

        converged = False
        for it in range(COORD_MAX_ITER):
            prev_auc = auc_current
            for key in MODULE_CAPS.keys():
                best_w = weights[key]
                best_auc = auc_current
                for w in w_grid:
                    trial = dict(weights)
                    trial[key] = float(w)
                    s = self._rescore(df, trial)
                    a = self._compute_auc(s, y)
                    if a > best_auc:
                        best_auc = a
                        best_w = float(w)
                weights[key] = best_w
                auc_current = best_auc

            improvement = auc_current - prev_auc
            logger.debug("Weight opt iter %d: AUC=%.4f (Δ+%.4f) weights=%s",
                         it + 1, auc_current, improvement, weights)
            if improvement < CONVERGENCE_TOL:
                converged = True
                break

        # Round weights to 2 decimal places
        weights = {k: round(v, 2) for k, v in weights.items()}

        return WeightOptResult(
            weights=weights,
            auc_baseline=round(auc_baseline, 4),
            auc_optimized=round(auc_current, 4),
            auc_improvement=round(auc_current - auc_baseline, 4),
            iterations=it + 1,
            converged=converged,
            n_used=len(y),
        )

    @staticmethod
    def _rescore(df: pd.DataFrame, weights: Dict[str, float]) -> np.ndarray:
        """Re-score each signal with given weight multipliers. Returns final_score array."""
        w_of    = weights.get("of",    1.0)
        w_smc   = weights.get("smc",   1.0)
        w_vsa   = weights.get("vsa",   1.0)
        w_ctx   = weights.get("ctx",   1.0)
        w_bonus = weights.get("bonus", 1.0)

        max_adj = 35.0*w_of + 30.0*w_smc + 30.0*w_vsa + 15.0*w_ctx + 15.0*w_bonus
        if max_adj == 0:
            return np.zeros(len(df))

        of_    = df["score_order_flow"].astype(float).fillna(0).values
        smc_   = df["score_smc"].astype(float).fillna(0).values
        vsa_   = df["score_vsa"].astype(float).fillna(0).values
        ctx_   = df["score_context"].astype(float).fillna(0).values
        bonus_ = df["score_bonus"].astype(float).fillna(0).values
        rm     = df["regime_multiplier"].astype(float).fillna(1.0).values

        raw_adj = of_*w_of + smc_*w_smc + vsa_*w_vsa + ctx_*w_ctx + bonus_*w_bonus
        final   = np.clip(np.round(raw_adj * rm / max_adj * 100).astype(int), 0, 100)
        return final

    @staticmethod
    def _compute_auc(scores: np.ndarray, y: np.ndarray) -> float:
        return WeightAnalyzer._auc_from_scores(scores, y)
