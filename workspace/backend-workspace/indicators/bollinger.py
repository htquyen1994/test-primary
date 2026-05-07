"""
Bollinger Bands
================
N-period, K standard deviations.
Returns (upper, middle, lower) Series, NaN for indices 0..N-2.

Satisfies: Requirements 4.2, 4.4, 4.5
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator


@dataclass
class BollingerResult:
    """Container for upper, middle (SMA), and lower band series."""
    upper: pd.Series
    middle: pd.Series
    lower: pd.Series


class BollingerBands(BaseIndicator):
    """
    Bollinger Bands.

    middle = SMA(close, N)
    std    = rolling standard deviation of close over N periods
    upper  = middle + K * std
    lower  = middle - K * std

    First valid value at index N-1.
    Indices 0..N-2 return NaN.
    """

    def compute(self, ohlcv: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Returns the middle band (SMA) for BaseIndicator compatibility.
        Use compute_full() to get all three bands.
        """
        return self.compute_full(ohlcv, period).middle

    def compute_full(
        self,
        ohlcv: pd.DataFrame,
        period: int = 20,
        k: float = 2.0,
    ) -> BollingerResult:
        """
        Args:
            ohlcv:  DataFrame with [open, high, low, close, volume]
            period: Rolling window (default 20)
            k:      Number of standard deviations (default 2.0)

        Returns:
            BollingerResult with upper, middle, lower Series
        """
        self._validate_ohlcv(ohlcv)
        n = len(ohlcv)

        nan_series = pd.Series(np.full(n, np.nan), index=ohlcv.index)

        if n < period:
            return BollingerResult(
                upper=nan_series.copy(),
                middle=nan_series.copy(),
                lower=nan_series.copy(),
            )

        close = ohlcv["close"].astype(float)

        # Rolling SMA and std (ddof=1 matches TradingView default)
        middle = close.rolling(window=period, min_periods=period).mean()
        std = close.rolling(window=period, min_periods=period).std(ddof=1)

        upper = middle + k * std
        lower = middle - k * std

        return BollingerResult(upper=upper, middle=middle, lower=lower)
