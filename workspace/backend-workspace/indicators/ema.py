"""
EMA — Exponential Moving Average
==================================
N-period EMA seeded with SMA of first N values.
Returns NaN for indices 0..N-2.

Satisfies: Requirements 4.2, 4.4, 4.5
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator


class EMA(BaseIndicator):
    """
    Exponential Moving Average.

    Seeded with SMA of first N closes, then:
    EMA[i] = EMA[i-1] * (1 - alpha) + close[i] * alpha
    where alpha = 2 / (period + 1)

    First valid value is at index N-1.
    Indices 0..N-2 return NaN.
    """

    def compute(self, ohlcv: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Args:
            ohlcv: DataFrame with [open, high, low, close, volume]
            period: EMA period (default 20)

        Returns:
            pd.Series of EMA values, NaN for 0..period-2
        """
        self._validate_ohlcv(ohlcv)
        n = len(ohlcv)

        if n == 0:
            return pd.Series(dtype=float)

        close = ohlcv["close"].values.astype(float)
        ema = np.full(n, np.nan)

        if n < period:
            return pd.Series(ema, index=ohlcv.index)

        alpha = 2.0 / (period + 1)

        # Seed with SMA of first `period` values
        ema[period - 1] = np.mean(close[:period])

        for i in range(period, n):
            ema[i] = ema[i - 1] * (1 - alpha) + close[i] * alpha

        return pd.Series(ema, index=ohlcv.index)
