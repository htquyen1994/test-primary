"""
Unit tests for Signal Scorer, Context Filter, and Confluence Bonus.

Satisfies: Requirements 6.1–6.6, 13.5
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.scorer import SignalScorer, ScoreInput, ScoreOutput
from engine.context import compute_context_score
from engine.confluence import compute_confluence_bonus, calc_fibonacci
from engine.smc import OrderBlock, FairValueGap


# ---------------------------------------------------------------------------
# SignalScorer tests
# ---------------------------------------------------------------------------

class TestSignalScorer:

    def setup_method(self):
        self.scorer = SignalScorer(alert_threshold=75, watch_threshold=55)

    def test_alert_at_threshold(self):
        # With all max scores and multiplier=1.0: raw=125, final=100
        result = self.scorer.score(ScoreInput(
            order_flow=35, smc=30, vsa=30, context=15, bonus=15,
            regime_multiplier=1.0, direction="long", regime="TRENDING",
        ))
        assert result.final_score == 100
        assert result.classification == "ALERT"

    def test_alert_classification_at_75(self):
        # raw = 93.75 → final = round(93.75/125*100) = 75
        result = self.scorer.score(ScoreInput(
            order_flow=35, smc=30, vsa=28.75, context=0, bonus=0,
            regime_multiplier=1.0, direction="long", regime="TRENDING",
        ))
        assert result.final_score == 75
        assert result.classification == "ALERT"

    def test_watch_classification(self):
        result = self.scorer.score(ScoreInput(
            order_flow=20, smc=15, vsa=10, context=5, bonus=0,
            regime_multiplier=1.0, direction="long", regime="TRENDING",
        ))
        assert result.classification in {"WATCH", "IGNORE"}

    def test_ignore_classification_at_zero(self):
        result = self.scorer.score(ScoreInput(
            order_flow=0, smc=0, vsa=0, context=0, bonus=0,
            regime_multiplier=1.0, direction="long", regime="TRENDING",
        ))
        assert result.final_score == 0
        assert result.classification == "IGNORE"

    def test_parabolic_suppresses_short(self):
        """Short signals must be IGNORE in PARABOLIC regime. Req 13.5"""
        result = self.scorer.score(ScoreInput(
            order_flow=35, smc=30, vsa=30, context=15, bonus=15,
            regime_multiplier=0.6, direction="short", regime="PARABOLIC",
        ))
        assert result.final_score == 0
        assert result.classification == "IGNORE"
        assert result.suppressed is True

    def test_parabolic_allows_long(self):
        """Long signals are NOT suppressed in PARABOLIC regime."""
        result = self.scorer.score(ScoreInput(
            order_flow=35, smc=30, vsa=30, context=15, bonus=15,
            regime_multiplier=0.6, direction="long", regime="PARABOLIC",
        ))
        assert result.suppressed is False
        assert result.final_score > 0

    def test_regime_multiplier_reduces_score(self):
        """0.6 multiplier should reduce score vs 1.0 multiplier."""
        full = self.scorer.score(ScoreInput(
            order_flow=35, smc=30, vsa=30, context=15, bonus=15,
            regime_multiplier=1.0, direction="long", regime="TRENDING",
        ))
        reduced = self.scorer.score(ScoreInput(
            order_flow=35, smc=30, vsa=30, context=15, bonus=15,
            regime_multiplier=0.6, direction="long", regime="PARABOLIC",
        ))
        assert reduced.final_score < full.final_score

    def test_score_bounded_0_to_100(self):
        for of in [0, 17.5, 35]:
            for mult in [0.6, 0.85, 1.0]:
                result = self.scorer.score(ScoreInput(
                    order_flow=of, smc=15, vsa=15, context=7, bonus=7,
                    regime_multiplier=mult, direction="long", regime="TRENDING",
                ))
                assert 0 <= result.final_score <= 100

    def test_invalid_thresholds_raise(self):
        with pytest.raises(ValueError):
            SignalScorer(alert_threshold=55, watch_threshold=75)  # watch >= alert

    def test_thresholds_from_config(self):
        from unittest.mock import MagicMock
        config = MagicMock()
        config.strategy.score_threshold.alert = 80
        config.strategy.score_threshold.watch = 60
        scorer = SignalScorer.from_config(config)
        assert scorer.alert_threshold == 80
        assert scorer.watch_threshold == 60


# ---------------------------------------------------------------------------
# Context Filter tests
# ---------------------------------------------------------------------------

class TestContextFilter:

    def _make_bullish_1h(self, n: int = 30) -> pd.DataFrame:
        closes = [100 + i for i in range(n)]
        return pd.DataFrame({
            "open": [c - 0.5 for c in closes],
            "high": [c + 1.0 for c in closes],
            "low":  [c - 1.0 for c in closes],
            "close": closes,
            "volume": [1000.0] * n,
        })

    def test_htf_bias_aligned_long_bullish(self):
        ohlcv_1h = self._make_bullish_1h()
        result = compute_context_score(ohlcv_1h, "long", 0.0001, 0.01)
        assert result.htf_bias_aligned is True
        assert result.score >= 8.0

    def test_funding_rate_neutral_bonus(self):
        result = compute_context_score(pd.DataFrame(), "long", 0.0003, 0.0)
        assert result.funding_rate_neutral is True
        assert result.score >= 4.0

    def test_funding_rate_extreme_no_bonus(self):
        result = compute_context_score(pd.DataFrame(), "long", 0.002, 0.0)
        assert result.funding_rate_neutral is False

    def test_price_away_from_sr_bonus(self):
        result = compute_context_score(pd.DataFrame(), "long", 0.002, 0.008)
        assert result.price_away_from_sr is True
        assert result.score >= 3.0

    def test_score_max_15(self):
        ohlcv_1h = self._make_bullish_1h()
        result = compute_context_score(ohlcv_1h, "long", 0.0001, 0.01)
        assert result.score <= 15.0


# ---------------------------------------------------------------------------
# Confluence Bonus tests
# ---------------------------------------------------------------------------

class TestConfluenceBonus:

    def _make_ohlcv(self, n: int = 60) -> pd.DataFrame:
        closes = [100 + i * 0.5 for i in range(n)]
        return pd.DataFrame({
            "open": [c - 0.3 for c in closes],
            "high": [c + 0.5 for c in closes],
            "low":  [c - 0.5 for c in closes],
            "close": closes,
            "volume": [1000.0] * n,
        })

    def test_no_ob_returns_zero(self):
        ohlcv = self._make_ohlcv()
        bonus = compute_confluence_bonus(ohlcv, ob_or_obs=None, fvg=None, poc=0.0)
        assert bonus == 0.0

    def test_invalid_ob_returns_zero(self):
        ob = OrderBlock(type="bullish", high=101, low=99, mid=100, candle_index=5, valid=False)
        ohlcv = self._make_ohlcv()
        bonus = compute_confluence_bonus(ohlcv, ob_or_obs=ob, fvg=None, poc=0.0)
        assert bonus == 0.0

    def test_bonus_non_negative(self):
        ohlcv = self._make_ohlcv()
        ob = OrderBlock(type="bullish", high=101, low=99, mid=100, candle_index=5)
        bonus = compute_confluence_bonus(ohlcv, ob_or_obs=ob, fvg=None, poc=0.0)
        assert bonus >= 0.0

    def test_bonus_max_15(self):
        ohlcv = self._make_ohlcv()
        ob = OrderBlock(type="bullish", high=101, low=99, mid=100, candle_index=5)
        fvg = FairValueGap(type="bullish", top=101, bot=99, mid=100, candle_index=3)
        bonus = compute_confluence_bonus(ohlcv, ob_or_obs=ob, fvg=fvg, poc=100.0)
        assert bonus <= 15.0

    def test_fibonacci_levels_computed(self):
        ohlcv = self._make_ohlcv(60)
        fibs = calc_fibonacci(ohlcv, lookback=50)
        assert "618" in fibs
        assert "500" in fibs
        assert "382" in fibs
        assert all(v > 0 for v in fibs.values())
