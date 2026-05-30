"""
Recommender
============
Synthesizes analysis results into concrete parameter recommendations.

Each recommendation has:
  param_name   : DB column in trading_params
  old_value    : current production value
  new_value    : proposed value
  reason       : human-readable explanation
  confidence   : "HIGH" | "MEDIUM" | "LOW"
  effect_size  : quantified improvement (EV delta, AUC delta, win-rate delta)
  min_sample   : minimum N used for this recommendation

Rules:
  - Only recommend changes with effect_size above EFFECT_THRESHOLD
  - Only recommend when sample N >= MIN_SAMPLE_PER_RECOMMENDATION
  - Threshold change: only when EV improvement > 0.05 (5% better outcome per trade)
  - Weight change: only when AUC improvement > 0.02 (2% better discrimination)
  - Regime block: only when win_rate < 0.35 and N >= 10
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .threshold_analyzer import ThresholdAnalysis
from .weight_analyzer import WeightAnalysis
from .regime_analyzer import RegimeAnalysis

logger = logging.getLogger(__name__)

# Thresholds for making recommendations
MIN_SAMPLE_THRESHOLD    = 20
MIN_SAMPLE_WEIGHT       = 15
MIN_SAMPLE_REGIME       = 10
EV_IMPROVEMENT_REQUIRED = 0.05    # 5% better EV to recommend threshold change
AUC_IMPROVEMENT_REQUIRED = 0.020  # 2% AUC gain to recommend weight change
THRESHOLD_MAX_JUMP       = 10     # never recommend > ±10 point threshold shift at once
WEIGHT_BOUNDS            = (0.25, 3.0)


@dataclass
class Recommendation:
    param_name: str
    param_group: str      # "threshold" | "weight" | "regime"
    old_value: float
    new_value: float
    reason: str
    confidence: str       # "HIGH" | "MEDIUM" | "LOW"
    effect_size: float    # e.g. EV delta, AUC delta, win_rate delta
    min_sample: int
    requires_restart: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TuningRecommendation:
    generated_at: str
    sample_n: int
    win_rate: float
    recommendations: List[Recommendation]
    summary: str
    apply_safe: bool       # True when all recs are HIGH/MEDIUM confidence
    current_auc: float
    optimized_auc: float

    def to_dict(self) -> dict:
        d = {
            "generated_at": self.generated_at,
            "sample_n": self.sample_n,
            "win_rate": self.win_rate,
            "current_auc": self.current_auc,
            "optimized_auc": self.optimized_auc,
            "apply_safe": self.apply_safe,
            "summary": self.summary,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }
        return d

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info("Recommendation saved → %s", path)


class Recommender:
    """
    Turns analysis results into actionable parameter changes.
    """

    def __init__(self, current_params: dict):
        """
        Args:
            current_params: dict from get_active_trading_params()
        """
        self._cp = current_params

    def recommend(
        self,
        threshold_analysis: ThresholdAnalysis,
        weight_analysis: WeightAnalysis,
        regime_analysis: RegimeAnalysis,
    ) -> TuningRecommendation:

        recs: List[Recommendation] = []
        n = threshold_analysis.total_labeled

        # ── 1. Threshold recommendation ──────────────────────────────────────
        recs += self._threshold_recs(threshold_analysis, n)

        # ── 2. Weight recommendations ────────────────────────────────────────
        recs += self._weight_recs(weight_analysis, n)

        # ── 3. Regime-based recommendations ─────────────────────────────────
        recs += self._regime_recs(regime_analysis, n)

        # ── Summary ─────────────────────────────────────────────────────────
        apply_safe = all(r.confidence in ("HIGH", "MEDIUM") for r in recs) if recs else False
        cur_stats  = threshold_analysis.current_stats
        opt_stats  = threshold_analysis.optimal_stats
        cur_ev  = cur_stats.ev  if cur_stats  else 0.0
        opt_ev  = opt_stats.ev  if opt_stats  else 0.0
        cur_wr  = cur_stats.precision if cur_stats else threshold_analysis.win_rate_overall
        cur_auc = weight_analysis.optimization.auc_baseline
        opt_auc = weight_analysis.optimization.auc_optimized

        if not recs:
            summary = (
                f"No tuning recommended (N={n} labeled signals, "
                f"win_rate={threshold_analysis.win_rate_overall:.1%}). "
                f"Current parameters appear near-optimal OR sample too small."
            )
        else:
            summary = (
                f"{len(recs)} change(s) recommended based on N={n} signals "
                f"(win_rate={threshold_analysis.win_rate_overall:.1%}, "
                f"current_EV={cur_ev:+.3f}, optimal_EV={opt_ev:+.3f}, "
                f"AUC {cur_auc:.3f}→{opt_auc:.3f})."
            )

        return TuningRecommendation(
            generated_at=datetime.now(timezone.utc).isoformat(),
            sample_n=n,
            win_rate=round(threshold_analysis.win_rate_overall, 4),
            recommendations=recs,
            summary=summary,
            apply_safe=apply_safe,
            current_auc=cur_auc,
            optimized_auc=opt_auc,
        )

    # ── Threshold ──────────────────────────────────────────────────────────────

    def _threshold_recs(self, ta: ThresholdAnalysis, n: int) -> List[Recommendation]:
        recs = []
        if n < MIN_SAMPLE_THRESHOLD:
            return recs

        cur_t = ta.current_threshold
        opt_t = ta.optimal_threshold
        cur_stats = ta.current_stats
        opt_stats = ta.optimal_stats

        if cur_t == opt_t or opt_stats is None or cur_stats is None:
            return recs

        ev_delta = opt_stats.ev - cur_stats.ev
        if abs(ev_delta) < EV_IMPROVEMENT_REQUIRED:
            return recs

        # Cap change at ±THRESHOLD_MAX_JUMP
        direction = 1 if opt_t > cur_t else -1
        capped_t = cur_t + direction * min(abs(opt_t - cur_t), THRESHOLD_MAX_JUMP)

        if abs(capped_t - cur_t) < 1:
            return recs

        confidence = "HIGH" if n >= 50 and abs(ev_delta) > 0.1 else "MEDIUM"

        recs.append(Recommendation(
            param_name="score_alert_threshold",
            param_group="threshold",
            old_value=float(cur_t),
            new_value=float(capped_t),
            reason=(
                f"Optimal threshold for max EV is {opt_t}. "
                f"At T={capped_t}: win_rate={opt_stats.precision:.1%}, "
                f"EV={opt_stats.ev:+.3f} vs current EV={cur_stats.ev:+.3f} "
                f"(Δ={ev_delta:+.3f} per trade, N={opt_stats.n_total} signals above)."
            ),
            confidence=confidence,
            effect_size=round(ev_delta, 4),
            min_sample=n,
        ))
        return recs

    # ── Weights ────────────────────────────────────────────────────────────────

    def _weight_recs(self, wa: WeightAnalysis, n: int) -> List[Recommendation]:
        recs = []
        if n < MIN_SAMPLE_WEIGHT or wa.insufficient_sample:
            return recs

        opt = wa.optimization
        if opt.auc_improvement < AUC_IMPROVEMENT_REQUIRED:
            return recs

        for key in ("of", "smc", "vsa", "ctx", "bonus"):
            param_map = {
                "of":    "weight_of",
                "smc":   "weight_smc",
                "vsa":   "weight_vsa",
                "ctx":   "weight_ctx",
                "bonus": "weight_bonus",
            }
            old_w = float(self._cp.get(f"weight_{key}", 1.0))
            new_w = opt.weights.get(key, 1.0)

            if abs(new_w - old_w) < 0.1:   # negligible change
                continue

            # Find corresponding module stats for reasoning
            ms = next((s for s in wa.module_stats if s.name == key), None)
            ms_info = (
                f"AUC={ms.auc_roc:.3f}, r={ms.correlation:+.3f}, p={ms.p_value:.3f}"
                if ms else "stats unavailable"
            )

            direction_word = "increase" if new_w > old_w else "decrease"
            significance = "significant" if (ms and ms.is_significant) else "marginal"

            recs.append(Recommendation(
                param_name=f"weight_{key}",
                param_group="weight",
                old_value=old_w,
                new_value=new_w,
                reason=(
                    f"{direction_word.capitalize()} weight for {key.upper()} module "
                    f"({old_w:.2f} → {new_w:.2f}). "
                    f"Module has {significance} predictive value ({ms_info}). "
                    f"Overall AUC improvement: +{opt.auc_improvement:.3f}."
                ),
                confidence="MEDIUM" if ms and ms.is_significant else "LOW",
                effect_size=round(opt.auc_improvement, 4),
                min_sample=n,
            ))

        return recs

    # ── Regime ────────────────────────────────────────────────────────────────

    def _regime_recs(self, ra: RegimeAnalysis, n: int) -> List[Recommendation]:
        recs = []
        if n < MIN_SAMPLE_REGIME:
            return recs

        for regime, stats in ra.regimes.items():
            if not stats.is_valid:
                continue
            if stats.recommendation == "BLOCK" and stats.n >= MIN_SAMPLE_REGIME:
                recs.append(Recommendation(
                    param_name=f"block_{regime.lower()}_regime",
                    param_group="regime",
                    old_value=0.0,
                    new_value=1.0,
                    reason=(
                        f"Regime {regime} has win_rate={stats.win_rate:.1%} (N={stats.n}) "
                        f"— well below breakeven. Consider blocking signals in this regime "
                        f"or raising threshold significantly."
                    ),
                    confidence="MEDIUM",
                    effect_size=round(0.5 - stats.win_rate, 4),
                    min_sample=stats.n,
                ))

        return recs
