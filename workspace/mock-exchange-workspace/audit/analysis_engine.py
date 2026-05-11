"""
AnalysisEngine — Q1-Q10 performance queries + tuning recommendations.
Pure query engine — no side effects.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from db.models import NoSignalAuditLog, SignalAuditLog, TradeAuditLog

logger = logging.getLogger(__name__)


def _wilson_ci(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 1.0)
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, round(centre - margin, 3)), min(1.0, round(centre + margin, 3)))


class AnalysisEngine:
    """
    Answers Q1-Q10 from trade_audit_log + signal_audit_log.
    Returns confidence-annotated performance report.
    """

    def __init__(self, db_factory) -> None:
        self._db_factory = db_factory

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    def get_performance_report(self, filters: Optional[dict] = None) -> dict:
        db: Session = self._db_factory()
        try:
            return self._build_report(db, filters or {})
        finally:
            db.close()

    def get_tuning_recommendations(self) -> dict:
        db: Session = self._db_factory()
        try:
            return self._build_tuning(db)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Internal report builder
    # ------------------------------------------------------------------

    def _build_report(self, db: Session, filters: dict) -> dict:
        trades = db.query(TradeAuditLog).filter(
            TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"])
        ).all()
        n = len(trades)
        confidence = self._confidence_level(n)

        # Q1: Overall win rate
        wins = [t for t in trades if t.outcome in ("TP1_HIT", "TP2_HIT")]
        win_rate = len(wins) / n if n > 0 else 0.0
        ci = _wilson_ci(win_rate, n)

        # Q2: Win rate by regime
        win_by_regime = self._win_rate_by_field(db, "regime")

        # Q3: Win rate by mtf_scenario
        win_by_mtf = self._win_rate_by_field(db, "mtf_scenario")

        # Q4: Win rate by score bucket
        win_by_bucket = self._win_rate_by_score_bucket(db)

        # Q5: Module correlation with true positives
        module_correlation = self._module_correlation(db)

        # Q6: Missed opportunity rate
        missed_opp_rate = self._missed_opportunity_rate(db)

        # Q7: SL hit reason distribution
        sl_reason_dist = self._sl_reason_distribution(trades)

        # Q8: ATR SL comparison
        atr_comparison = self._atr_sl_comparison(db)

        # Q9: Win rate by hour of day
        win_by_hour = self._win_rate_by_hour(db)

        # Q10: Funding rate correlation
        funding_correlation = self._funding_rate_correlation(db)

        # Optimal score threshold suggestion
        optimal_threshold = self._suggest_optimal_threshold(db)

        return {
            "sample_size": n,
            "confidence": confidence,
            "confidence_note": self._confidence_note(confidence, n),
            "win_rate": {
                "value": round(win_rate, 3),
                "ci_95": list(ci),
            },
            "win_rate_by_regime": win_by_regime,
            "win_rate_by_mtf_scenario": win_by_mtf,
            "win_rate_by_score_bucket": win_by_bucket,
            "optimal_threshold_suggestion": optimal_threshold,
            "module_correlation": module_correlation,
            "missed_opportunity_rate": missed_opp_rate,
            "sl_hit_reasons": sl_reason_dist,
            "atr_sl_comparison": atr_comparison,
            "win_rate_by_hour": win_by_hour,
            "funding_rate_correlation": funding_correlation,
            "questions": self._format_questions(
                n, win_rate, win_by_regime, win_by_mtf,
                win_by_bucket, sl_reason_dist, missed_opp_rate,
                optimal_threshold,
            ),
        }

    # ------------------------------------------------------------------
    # Q2: Win rate by regime
    # ------------------------------------------------------------------

    def _win_rate_by_field(self, db: Session, field_name: str) -> dict:
        """Join trade_audit_log with signal_audit_log, group by field."""
        try:
            rows = (
                db.query(
                    getattr(SignalAuditLog, field_name),
                    TradeAuditLog.outcome,
                )
                .join(TradeAuditLog, TradeAuditLog.signal_audit_id == SignalAuditLog.id)
                .filter(TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"]))
                .all()
            )
        except Exception as exc:
            logger.warning("_win_rate_by_field failed for %s: %s", field_name, exc)
            return {}

        buckets: dict[str, list] = defaultdict(list)
        for field_val, outcome in rows:
            key = str(field_val) if field_val else "UNKNOWN"
            buckets[key].append(outcome in ("TP1_HIT", "TP2_HIT"))

        return {
            k: round(sum(v) / len(v), 3) if v else 0.0
            for k, v in buckets.items()
        }

    # ------------------------------------------------------------------
    # Q4: Win rate by score bucket
    # ------------------------------------------------------------------

    def _win_rate_by_score_bucket(self, db: Session) -> dict:
        try:
            rows = (
                db.query(SignalAuditLog.final_score, TradeAuditLog.outcome)
                .join(TradeAuditLog, TradeAuditLog.signal_audit_id == SignalAuditLog.id)
                .filter(TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"]))
                .all()
            )
        except Exception as exc:
            logger.warning("_win_rate_by_score_bucket failed: %s", exc)
            return {}

        buckets: dict[str, list] = defaultdict(list)
        for score, outcome in rows:
            if score is None:
                continue
            if score < 80:
                bucket = "75-79"
            elif score < 85:
                bucket = "80-84"
            else:
                bucket = "85+"
            buckets[bucket].append(outcome in ("TP1_HIT", "TP2_HIT"))

        return {
            k: round(sum(v) / len(v), 3) if v else 0.0
            for k, v in sorted(buckets.items())
        }

    # ------------------------------------------------------------------
    # Q5: Module correlation
    # ------------------------------------------------------------------

    def _module_correlation(self, db: Session) -> dict:
        """Which score_breakdown modules correlate most with TRUE_POSITIVE."""
        try:
            rows = (
                db.query(SignalAuditLog.score_breakdown, TradeAuditLog.signal_quality_verdict)
                .join(TradeAuditLog, TradeAuditLog.signal_audit_id == SignalAuditLog.id)
                .filter(
                    SignalAuditLog.score_breakdown.isnot(None),
                    TradeAuditLog.signal_quality_verdict.isnot(None),
                )
                .all()
            )
        except Exception:
            return {}

        module_wins: dict[str, list] = defaultdict(list)
        for breakdown_json, verdict in rows:
            try:
                breakdown = json.loads(breakdown_json) if breakdown_json else {}
            except json.JSONDecodeError:
                continue
            is_win = verdict == "TRUE_POSITIVE"
            for module, value in breakdown.items():
                if isinstance(value, (int, float)):
                    module_wins[module].append((float(value), is_win))

        result = {}
        for module, pairs in module_wins.items():
            if not pairs:
                continue
            win_values = [v for v, w in pairs if w]
            lose_values = [v for v, w in pairs if not w]
            avg_win = sum(win_values) / len(win_values) if win_values else 0.0
            avg_lose = sum(lose_values) / len(lose_values) if lose_values else 0.0
            result[module] = {
                "avg_score_on_win": round(avg_win, 2),
                "avg_score_on_loss": round(avg_lose, 2),
                "difference": round(avg_win - avg_lose, 2),
            }

        return result

    # ------------------------------------------------------------------
    # Q6: Missed opportunity rate
    # ------------------------------------------------------------------

    def _missed_opportunity_rate(self, db: Session) -> float:
        try:
            total = db.query(func.count(NoSignalAuditLog.id)).scalar() or 0
            missed = db.query(func.count(NoSignalAuditLog.id)).filter(
                NoSignalAuditLog.missed_opportunity == 1
            ).scalar() or 0
            return round(missed / total, 3) if total > 0 else 0.0
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Q7: SL reason distribution
    # ------------------------------------------------------------------

    def _sl_reason_distribution(self, trades: list) -> dict:
        sl_trades = [t for t in trades if t.outcome == "SL_HIT" and t.sl_hit_reason]
        if not sl_trades:
            return {}
        n = len(sl_trades)
        dist: dict[str, int] = defaultdict(int)
        for t in sl_trades:
            dist[t.sl_hit_reason] += 1
        return {k: round(v / n, 3) for k, v in dist.items()}

    # ------------------------------------------------------------------
    # Q8: ATR SL comparison (would_have_hit_sl vs fixed 2%)
    # ------------------------------------------------------------------

    def _atr_sl_comparison(self, db: Session) -> dict:
        try:
            rows = (
                db.query(
                    SignalAuditLog.would_have_hit_sl,
                    SignalAuditLog.entry_price_proposed,
                    SignalAuditLog.sl_proposed,
                    SignalAuditLog.atr_value,
                )
                .filter(
                    SignalAuditLog.audit_status == "COMPLETE",
                    SignalAuditLog.entry_price_proposed.isnot(None),
                    SignalAuditLog.sl_proposed.isnot(None),
                )
                .all()
            )
        except Exception:
            return {}

        if not rows:
            return {}

        atr_sl_hit = sum(1 for r in rows if r[0] == 1)
        fixed_sl_hit = 0
        for would_hit, entry, sl, atr in rows:
            if entry and sl:
                atr_sl_pct = abs(entry - sl) / entry * 100
                fixed_sl = entry * 0.98  # 2% fixed
                # Would fixed 2% SL have been triggered? (rough comparison)
                if atr_sl_pct > 2.0:
                    fixed_sl_hit += 1 if would_hit else 0

        n = len(rows)
        return {
            "atr_sl_hit_rate": round(atr_sl_hit / n, 3) if n > 0 else 0.0,
            "fixed_2pct_sl_hit_rate_estimate": round(fixed_sl_hit / n, 3) if n > 0 else 0.0,
            "sample_count": n,
        }

    # ------------------------------------------------------------------
    # Q9: Win rate by hour of day
    # ------------------------------------------------------------------

    def _win_rate_by_hour(self, db: Session) -> dict:
        try:
            rows = (
                db.query(
                    SignalAuditLog.timestamp_candle_close,
                    TradeAuditLog.outcome,
                )
                .join(TradeAuditLog, TradeAuditLog.signal_audit_id == SignalAuditLog.id)
                .filter(TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"]))
                .all()
            )
        except Exception:
            return {}

        buckets: dict[int, list] = defaultdict(list)
        for ts_str, outcome in rows:
            try:
                hour = int(ts_str[11:13]) if ts_str and len(ts_str) >= 13 else 0
                buckets[hour].append(outcome in ("TP1_HIT", "TP2_HIT"))
            except Exception:
                pass

        return {
            str(hour): round(sum(v) / len(v), 3) if v else 0.0
            for hour, v in sorted(buckets.items())
        }

    # ------------------------------------------------------------------
    # Q10: Funding rate correlation
    # ------------------------------------------------------------------

    def _funding_rate_correlation(self, db: Session) -> dict:
        try:
            rows = (
                db.query(SignalAuditLog.funding_rate, TradeAuditLog.outcome)
                .join(TradeAuditLog, TradeAuditLog.signal_audit_id == SignalAuditLog.id)
                .filter(
                    SignalAuditLog.funding_rate.isnot(None),
                    TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"]),
                )
                .all()
            )
        except Exception:
            return {}

        if not rows:
            return {"note": "Insufficient data"}

        high_funding = [(r, o) for r, o in rows if r > 0.001]
        low_funding = [(r, o) for r, o in rows if r <= 0.001]

        def _wr(pairs):
            if not pairs:
                return 0.0
            return round(sum(1 for _, o in pairs if o in ("TP1_HIT", "TP2_HIT")) / len(pairs), 3)

        return {
            "high_funding_win_rate": _wr(high_funding),
            "low_funding_win_rate": _wr(low_funding),
            "high_funding_sample": len(high_funding),
            "low_funding_sample": len(low_funding),
        }

    # ------------------------------------------------------------------
    # Optimal threshold suggestion
    # ------------------------------------------------------------------

    def _suggest_optimal_threshold(self, db: Session) -> Optional[int]:
        """Suggest a score threshold that maximizes win rate × sample size."""
        try:
            rows = (
                db.query(SignalAuditLog.final_score, TradeAuditLog.outcome)
                .join(TradeAuditLog, TradeAuditLog.signal_audit_id == SignalAuditLog.id)
                .filter(TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"]))
                .all()
            )
        except Exception:
            return None

        if len(rows) < 10:
            return None

        best_threshold = 75
        best_f1 = 0.0
        for threshold in range(75, 95, 5):
            above = [o for s, o in rows if s is not None and s >= threshold]
            if not above:
                continue
            wr = sum(1 for o in above if o in ("TP1_HIT", "TP2_HIT")) / len(above)
            coverage = len(above) / len(rows)
            f1 = 2 * wr * coverage / (wr + coverage) if (wr + coverage) > 0 else 0
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold

        return best_threshold

    # ------------------------------------------------------------------
    # Tuning recommendations
    # ------------------------------------------------------------------

    def _build_tuning(self, db: Session) -> dict:
        trades = db.query(TradeAuditLog).filter(
            TradeAuditLog.audit_status.in_(["ANALYZED", "REVIEWED"])
        ).all()
        n = len(trades)
        confidence = self._confidence_level(n)

        if confidence == "insufficient":
            return {
                "confidence": confidence,
                "sample_size": n,
                "note": "Insufficient data for tuning recommendations. Need at least 10 trades.",
                "recommendations": [],
            }

        recs = []

        # Score threshold recommendation
        threshold = self._suggest_optimal_threshold(db)
        if threshold:
            recs.append({
                "type": "score_threshold",
                "current": 75,
                "suggested": threshold,
                "rationale": "Maximizes win_rate × coverage trade-off",
                "confidence": confidence,
            })

        # Regime-specific adjustments
        win_by_regime = self._win_rate_by_field(db, "regime")
        for regime, wr in win_by_regime.items():
            if wr < 0.4 and regime != "UNKNOWN":
                recs.append({
                    "type": "regime_filter",
                    "regime": regime,
                    "win_rate": wr,
                    "suggestion": f"Consider filtering signals in {regime} regime (win rate: {wr:.1%})",
                    "confidence": confidence,
                })

        # SL hit reasons
        sl_reasons = self._sl_reason_distribution(trades)
        if sl_reasons.get("NOISE", 0) > 0.4:
            recs.append({
                "type": "atr_multiplier",
                "suggestion": "High NOISE rate — consider increasing ATR multiplier for SL",
                "noise_rate": sl_reasons["NOISE"],
                "confidence": confidence,
            })

        return {
            "confidence": confidence,
            "sample_size": n,
            "recommendations": recs,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _confidence_level(n: int) -> str:
        if n < 10:
            return "insufficient"
        if n < 20:
            return "very_low"
        if n < 30:
            return "low"
        if n < 50:
            return "medium"
        return "high"

    @staticmethod
    def _confidence_note(confidence: str, n: int) -> str:
        notes = {
            "insufficient": f"Only {n} trades. Results are not statistically meaningful.",
            "very_low": f"Based on {n} trades. Very wide confidence intervals.",
            "low": f"Based on {n} trades. Results are directional.",
            "medium": f"Based on {n} trades. Moderate confidence.",
            "high": f"Based on {n} trades. High confidence.",
        }
        return notes.get(confidence, f"Based on {n} trades.")

    @staticmethod
    def _format_questions(
        n, win_rate, win_by_regime, win_by_mtf,
        win_by_bucket, sl_reasons, missed_opp_rate, threshold,
    ) -> dict:
        return {
            "Q1": f"Overall win rate: {win_rate:.1%} (n={n})",
            "Q2": f"Win rate by regime: {win_by_regime}",
            "Q3": f"Win rate by MTF scenario: {win_by_mtf}",
            "Q4": f"Win rate by score bucket: {win_by_bucket}",
            "Q5": "See module_correlation field",
            "Q6": f"Missed opportunity rate: {missed_opp_rate:.1%}",
            "Q7": f"SL hit reasons: {sl_reasons}",
            "Q8": "See atr_sl_comparison field",
            "Q9": "See win_rate_by_hour field",
            "Q10": "See funding_rate_correlation field",
        }
