"""
Report Writer
==============
Generates a human-readable Markdown tuning report from all analysis results.

Output: YYYY-MM-DD/tuning/tuning_report.md
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .threshold_analyzer import ThresholdAnalysis, ThresholdStats
from .weight_analyzer import WeightAnalysis
from .regime_analyzer import RegimeAnalysis
from .recommender import TuningRecommendation

logger = logging.getLogger(__name__)


class ReportWriter:

    def write(
        self,
        out_path: Path,
        threshold_analysis: ThresholdAnalysis,
        weight_analysis: WeightAnalysis,
        regime_analysis: RegimeAnalysis,
        recommendation: TuningRecommendation,
        apply_result: Optional[dict] = None,
    ) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        lines = self._build(
            threshold_analysis, weight_analysis,
            regime_analysis, recommendation, apply_result,
        )
        out_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Tuning report written → %s", out_path)

    # ── Builder ────────────────────────────────────────────────────────────────

    def _build(
        self, ta: ThresholdAnalysis, wa: WeightAnalysis,
        ra: RegimeAnalysis, rec: TuningRecommendation,
        apply_result: Optional[dict],
    ) -> list[str]:

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        L = []

        L += [
            f"# Threshold Optimization Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"> Generated: {now}  ",
            f"> Sample: **{ta.total_labeled} labeled signals** "
            f"(WIN={ta.total_win}, LOSS={ta.total_loss})  ",
            f"> Overall win rate: **{ta.win_rate_overall:.1%}**",
            "",
        ]

        # ── 0. Executive Summary ──────────────────────────────────────────────
        L += ["## Executive Summary", ""]
        L.append(rec.summary)
        L.append("")

        if rec.recommendations:
            L.append(f"**{len(rec.recommendations)} recommendation(s):**")
            L.append("")
            for r in rec.recommendations:
                arrow = "↑" if r.new_value > r.old_value else "↓"
                L.append(
                    f"- [{r.confidence}] **{r.param_name}**: "
                    f"{r.old_value} {arrow} {r.new_value} "
                    f"(effect={r.effect_size:+.3f})"
                )
            L.append("")
        else:
            L.append("No changes recommended at this time.")
            L.append("")

        # ── 1. Threshold Analysis ─────────────────────────────────────────────
        L += ["---", "## 1. Threshold Analysis", ""]

        cur = ta.current_stats
        opt = ta.optimal_stats

        if cur:
            L += [
                f"**Current threshold (T={ta.current_threshold}):**",
                f"- Alerts generated: {cur.n_total} | Precision: {cur.precision:.1%} "
                f"| Recall: {cur.recall:.1%} | EV: {cur.ev:+.3f}",
                "",
            ]
        if opt:
            L += [
                f"**Optimal threshold (T={ta.optimal_threshold}):**",
                f"- Alerts generated: {opt.n_total} | Precision: {opt.precision:.1%} "
                f"| Recall: {opt.recall:.1%} | EV: {opt.ev:+.3f} "
                f"[CI {opt.ev_ci_low:+.3f} – {opt.ev_ci_high:+.3f}]",
                "",
            ]

        # Score bucket table
        if ta.buckets:
            L += ["### Win Rate by Score Bucket", ""]
            L.append("| Score Range | N | Win Rate | Avg R:R | EV/trade |")
            L.append("|------------|--:|--------:|-------:|--------:|")
            for bucket, b in sorted(ta.buckets.items()):
                flag = " ◀ current" if ta.current_threshold and bucket.startswith(str(ta.current_threshold)[:2]) else ""
                L.append(
                    f"| {bucket} | {b['n']} | {b['win_rate']:.1%} "
                    f"| {b['avg_rr']:.2f} | {b['ev']:+.3f} |{flag}"
                )
            L.append("")

        # EV curve (top 10 thresholds)
        valid_curve = [s for s in ta.curve if s.is_valid]
        if valid_curve:
            L += ["### EV Curve (valid thresholds only)", ""]
            L.append("| T | N | Precision | Recall | F1 | EV | EV CI |")
            L.append("|--:|--:|---------:|------:|---:|---:|------|")
            # Show every 5th threshold + current + optimal
            shown = {ta.current_threshold, ta.optimal_threshold}
            shown |= {s.threshold for s in valid_curve[::5]}
            for s in valid_curve:
                if s.threshold not in shown:
                    continue
                marker = ""
                if s.threshold == ta.current_threshold:
                    marker = " ◀ current"
                elif s.threshold == ta.optimal_threshold:
                    marker = " ◀ optimal"
                L.append(
                    f"| {s.threshold} | {s.n_total} | {s.precision:.1%} "
                    f"| {s.recall:.1%} | {s.f1:.3f} | {s.ev:+.3f} "
                    f"| [{s.ev_ci_low:+.3f}, {s.ev_ci_high:+.3f}] |{marker}"
                )
            L.append("")

        # ── 2. Module Weight Analysis ─────────────────────────────────────────
        L += ["---", "## 2. Module Predictiveness", ""]

        if wa.insufficient_sample:
            L.append(
                f"> ⚠ Insufficient sample (N={wa.sample_n}) for reliable weight optimization. "
                f"Need ≥ 15 labeled signals."
            )
            L.append("")

        if wa.module_stats:
            L.append("### Module Importance Ranking")
            L.append("")
            L.append("| Rank | Module | AUC-ROC | Correlation | Cohen's d | p-value | Mean(WIN) | Mean(LOSS) | Predictive? |")
            L.append("|-----:|-------|-------:|----------:|--------:|-------:|--------:|----------:|------------|")
            for ms in wa.module_stats:
                sig = "✓ Yes" if ms.is_significant else "✗ No"
                L.append(
                    f"| {ms.importance_rank} | **{ms.name.upper()}** "
                    f"| {ms.auc_roc:.3f} | {ms.correlation:+.3f} "
                    f"| {ms.cohens_d:+.3f} | {ms.p_value:.3f} "
                    f"| {ms.mean_win:.1f} | {ms.mean_loss:.1f} | {sig} |"
                )
            L.append("")

        opt = wa.optimization
        L += [
            "### Weight Optimization Result",
            "",
            f"- Baseline AUC (all weights = 1.0): **{opt.auc_baseline:.4f}**",
            f"- Optimized AUC: **{opt.auc_optimized:.4f}** (Δ +{opt.auc_improvement:.4f})",
            f"- Converged: {opt.converged} (iterations: {opt.iterations})",
            f"- Sample used: N={opt.n_used}",
            "",
        ]

        if abs(opt.auc_improvement) > 0.005:
            L.append("**Proposed weight multipliers:**")
            L.append("")
            L.append("| Module | Current | Proposed | Direction |")
            L.append("|--------|--------:|---------:|----------|")
            for k, v in opt.weights.items():
                old = 1.0  # always 1.0 as baseline
                arrow = "↑ increase" if v > old else ("↓ decrease" if v < old else "→ unchanged")
                L.append(f"| {k.upper()} | {old:.2f} | {v:.2f} | {arrow} |")
            L.append("")
        else:
            L.append("Weight changes provide negligible improvement — current weights are near-optimal.")
            L.append("")

        # ── 3. Regime Analysis ────────────────────────────────────────────────
        L += ["---", "## 3. Regime Analysis", ""]

        if ra.regimes:
            L.append("| Regime | N | Win Rate | Avg Score | Avg MAE% | Avg MFE% | Recommendation |")
            L.append("|--------|--:|--------:|--------:|---------:|---------:|---------------|")
            for regime, rs in sorted(ra.regimes.items(), key=lambda x: -x[1].win_rate):
                valid_flag = "" if rs.is_valid else " *(insufficient)*"
                L.append(
                    f"| {regime} | {rs.n} | {rs.win_rate:.1%} "
                    f"| {rs.avg_score:.0f} | {rs.avg_mae:.2f}% | {rs.avg_mfe:.2f}% "
                    f"| **{rs.recommendation}**{valid_flag} |"
                )
            L.append("")

            if ra.block_candidates:
                L.append(
                    f"> ⚠ **Regime block candidates:** {', '.join(ra.block_candidates)} "
                    f"— win rate below 40%. Consider adding circuit-breaker logic."
                )
                L.append("")
        else:
            L.append("No regime data available.")
            L.append("")

        # ── 4. Recommendations ────────────────────────────────────────────────
        L += ["---", "## 4. Recommendations", ""]

        if not rec.recommendations:
            L.append("No parameter changes recommended at this time.")
        else:
            for i, r in enumerate(rec.recommendations, 1):
                conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(r.confidence, "⚪")
                L += [
                    f"### Rec {i}: `{r.param_name}` ({r.param_group})",
                    f"{conf_emoji} **Confidence: {r.confidence}** | "
                    f"Effect size: {r.effect_size:+.4f} | "
                    f"Sample: N={r.min_sample}",
                    "",
                    f"- Current value: `{r.old_value}`",
                    f"- Proposed value: `{r.new_value}`",
                    f"- Reason: {r.reason}",
                    "",
                ]
        L.append("")

        # ── 5. Apply Result ───────────────────────────────────────────────────
        if apply_result is not None:
            L += ["---", "## 5. Apply Result", ""]
            if apply_result.get("dry_run"):
                L.append("> 🔵 **DRY-RUN** — no changes written to DB.")
            elif apply_result.get("applied"):
                L.append(f"> ✅ **Applied** — new version: `{apply_result.get('new_version_tag')}`")
            else:
                L.append(f"> ❌ **Not applied** — {apply_result.get('error', 'unknown error')}")
            L.append("")
            if apply_result.get("changes"):
                L.append("**Changes written:**")
                for c in apply_result["changes"]:
                    L.append(f"- `{c['param']}`: {c['old']} → {c['new']}")
                L.append("")
            if apply_result.get("skipped"):
                L.append("**Skipped:**")
                for s in apply_result["skipped"]:
                    L.append(f"- {s.get('param', '?')}: {s.get('reason', '')}")
                L.append("")

        # ── 6. How to Apply ───────────────────────────────────────────────────
        L += [
            "---",
            "## 6. How to Apply",
            "",
            "```bash",
            "# Dry-run (default — shows what would change, no DB write)",
            "python threshold_optimizer.py --step=all",
            "",
            "# Apply recommendations to DB",
            "python threshold_optimizer.py --step=all --apply",
            "",
            "# Apply only threshold change",
            "python threshold_optimizer.py --step=apply --apply",
            "```",
            "",
            "> After applying, **restart the pipeline** (`python main.py`) to pick up",
            "> the new weights and thresholds from DB.",
            "",
            "---",
            f"*Report generated by threshold_optimizer.py — {now}*",
        ]

        return L
