"""
Regime Detector
================
Classifies the current market state for each asset.
Output drives the Score_Multiplier applied to all signals.

States (priority order — PARABOLIC checked first):
  PARABOLIC : ATR(14) on 15m > atr_parabolic_multiplier × rolling_avg_ATR(14)
              → Score_Multiplier = 0.6, suppress all Short signals
  TRENDING  : ADX(14) on 1h > adx_trending_threshold (default 25)
              → Score_Multiplier = 1.0
  CHOPPY    : ADX(14) on 1h < adx_choppy_threshold (default 20)
              → Score_Multiplier = 0.85
  RANGING   : 20 ≤ ADX ≤ 25 (between thresholds)
              → Score_Multiplier = 0.85

Satisfies: Requirements 13.1–13.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from indicators.atr import ATR
from indicators.adx import ADX

logger = logging.getLogger(__name__)

# Default thresholds (all configurable via config.yaml)
DEFAULT_ADX_TRENDING = 25.0
DEFAULT_ADX_CHOPPY = 20.0
DEFAULT_ATR_PARABOLIC_MULT = 3.0
DEFAULT_ATR_ROLLING_WINDOW = 20

# Score multipliers
MULTIPLIER_TRENDING = 1.0
MULTIPLIER_RANGING = 0.85
MULTIPLIER_CHOPPY = 0.85
MULTIPLIER_PARABOLIC = 0.6

VALID_REGIMES = frozenset({"TRENDING", "RANGING", "PARABOLIC", "CHOPPY"})


@dataclass
class RegimeState:
    """
    Output of the Regime Detector for a single asset.

    Satisfies: Requirement 13.8 (consistent interface for Signal_Scorer)
    """
    regime: str             # "TRENDING" | "RANGING" | "PARABOLIC" | "CHOPPY"
    score_multiplier: float # applied to raw signal score
    suppress_short: bool    # True only in PARABOLIC regime

    def __post_init__(self) -> None:
        if self.regime not in VALID_REGIMES:
            raise ValueError(
                f"RegimeState.regime must be one of {VALID_REGIMES}, "
                f"got '{self.regime}'"
            )


class RegimeDetector:
    """
    Classifies market regime from 1h ADX and 15m ATR.

    Priority order (PARABOLIC takes precedence over ADX-based states):
    1. PARABOLIC  — ATR spike check (highest priority)
    2. TRENDING   — ADX > trending threshold
    3. CHOPPY     — ADX < choppy threshold
    4. RANGING    — default (between thresholds)

    Satisfies: Requirements 13.1–13.9
    """

    def __init__(
        self,
        adx_trending_threshold: float = DEFAULT_ADX_TRENDING,
        adx_choppy_threshold: float = DEFAULT_ADX_CHOPPY,
        atr_parabolic_multiplier: float = DEFAULT_ATR_PARABOLIC_MULT,
        atr_rolling_window: int = DEFAULT_ATR_ROLLING_WINDOW,
        parabolic_score_multiplier: float = MULTIPLIER_PARABOLIC,
        ranging_score_multiplier: float = MULTIPLIER_RANGING,
        trending_score_multiplier: float = MULTIPLIER_TRENDING,
    ) -> None:
        self.adx_trending_threshold = adx_trending_threshold
        self.adx_choppy_threshold = adx_choppy_threshold
        self.atr_parabolic_multiplier = atr_parabolic_multiplier
        self.atr_rolling_window = atr_rolling_window
        self.parabolic_score_multiplier = parabolic_score_multiplier
        self.ranging_score_multiplier = ranging_score_multiplier
        self.trending_score_multiplier = trending_score_multiplier

    @classmethod
    def from_config(cls, config) -> "RegimeDetector":
        """
        Create a RegimeDetector from a validated AppConfig object.
        All thresholds sourced from config (Req 13.9).
        """
        r = config.regime
        return cls(
            adx_trending_threshold=r.adx_trending_threshold,
            adx_choppy_threshold=r.adx_choppy_threshold,
            atr_parabolic_multiplier=r.atr_parabolic_multiplier,
            atr_rolling_window=20,
            parabolic_score_multiplier=r.parabolic_score_multiplier,
            ranging_score_multiplier=r.ranging_score_multiplier,
            trending_score_multiplier=r.trending_score_multiplier,
        )

    def classify(
        self,
        ohlcv_1h: pd.DataFrame,
        ohlcv_15m: pd.DataFrame,
    ) -> RegimeState:
        """
        Classify the current market regime.

        Args:
            ohlcv_1h:  1-hour OHLCV DataFrame (for ADX)
            ohlcv_15m: 15-minute OHLCV DataFrame (for ATR spike)

        Returns:
            RegimeState — always returns exactly one of the four valid states.
            Never returns None or an undefined state (Property 12).

        Satisfies: Requirements 13.1–13.8
        """
        # --- Priority 1: PARABOLIC check (ATR spike on 15m) ---
        # Must run BEFORE ADX check because ADX can be high during parabolic moves
        if self._is_parabolic(ohlcv_15m):
            logger.debug("Regime: PARABOLIC (ATR spike detected)")
            return RegimeState(
                regime="PARABOLIC",
                score_multiplier=self.parabolic_score_multiplier,
                suppress_short=True,  # Req 13.5
            )

        # --- Priority 2: ADX-based classification (on 1h) ---
        adx_value = self._get_adx(ohlcv_1h)

        if adx_value is not None:
            # TRENDING: ADX > trending threshold (Req 13.2)
            if adx_value > self.adx_trending_threshold:
                logger.debug("Regime: TRENDING (ADX=%.1f)", adx_value)
                return RegimeState(
                    regime="TRENDING",
                    score_multiplier=self.trending_score_multiplier,
                    suppress_short=False,
                )

            # CHOPPY: ADX < choppy threshold (Req 13.3)
            if adx_value < self.adx_choppy_threshold:
                logger.debug("Regime: CHOPPY (ADX=%.1f)", adx_value)
                return RegimeState(
                    regime="CHOPPY",
                    score_multiplier=self.ranging_score_multiplier,
                    suppress_short=False,
                )

        # --- Default: RANGING (between thresholds or insufficient data) ---
        logger.debug("Regime: RANGING (ADX=%.1f)", adx_value or 0)
        return RegimeState(
            regime="RANGING",
            score_multiplier=self.ranging_score_multiplier,
            suppress_short=False,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_parabolic(self, ohlcv_15m: pd.DataFrame) -> bool:
        """
        Returns True if current ATR(14) on 15m exceeds
        atr_parabolic_multiplier × rolling_avg_ATR(14).

        Satisfies: Requirement 13.4
        """
        n = len(ohlcv_15m)
        min_required = 14 + self.atr_rolling_window
        if n < min_required:
            return False

        atr_series = ATR().compute(ohlcv_15m, period=14)
        valid_atr = atr_series.dropna()

        if len(valid_atr) < self.atr_rolling_window:
            return False

        current_atr = float(valid_atr.iloc[-1])
        rolling_avg = float(valid_atr.iloc[-self.atr_rolling_window:].mean())

        if rolling_avg == 0:
            return False

        is_spike = current_atr > self.atr_parabolic_multiplier * rolling_avg
        if is_spike:
            logger.debug(
                "ATR spike: current=%.4f, rolling_avg=%.4f, ratio=%.2f",
                current_atr, rolling_avg, current_atr / rolling_avg,
            )
        return is_spike

    def _get_adx(self, ohlcv_1h: pd.DataFrame) -> Optional[float]:
        """
        Compute ADX(14) on 1h data.
        Returns None if insufficient data.
        """
        min_required = 2 * 14  # ADX needs 2*period candles
        if len(ohlcv_1h) < min_required:
            return None

        adx_series = ADX().compute(ohlcv_1h, period=14)
        valid = adx_series.dropna()

        if valid.empty:
            return None

        val = float(valid.iloc[-1])
        return val if not np.isnan(val) else None
