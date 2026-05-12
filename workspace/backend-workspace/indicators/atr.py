"""
ATR — Average True Range
=========================
N-period ATR using Wilder smoothing (same as TradingView default).
Returns NaN for indices 0..N-2.

Satisfies: Requirements 4.2, 4.4, 4.5
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator


class ATR(BaseIndicator):
    """
    Average True Range (Wilder smoothing).

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR[N] = Wilder EMA of True Range over N periods

    First valid value is at index N (requires N+1 candles).
    Indices 0..N-1 return NaN.
    """

    def compute(self, ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Args:
            ohlcv: DataFrame with [open, high, low, close, volume]
            period: ATR period (default 14)

        Returns:
            pd.Series of ATR values, same length as ohlcv, NaN for 0..period-1
        """
        self._validate_ohlcv(ohlcv)
        n = len(ohlcv)

        if n == 0:
            return pd.Series(dtype=float)

        high = ohlcv["high"].values.astype(float)
        low = ohlcv["low"].values.astype(float)
        close = ohlcv["close"].values.astype(float)

        # True Range
        tr = np.empty(n)
        tr[0] = high[0] - low[0]  # first bar: no previous close
        for i in range(1, n):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        # Wilder smoothing: SMA for first value, then EMA with alpha=1/period
        atr = np.full(n, np.nan)
        if n < period:
            return pd.Series(atr, index=ohlcv.index)

        # Seed with simple average of first `period` true ranges
        atr[period - 1] = np.mean(tr[:period])

        # Wilder EMA: ATR[i] = ATR[i-1] * (period-1)/period + TR[i] * 1/period
        alpha = 1.0 / period
        for i in range(period, n):
            atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha

        return pd.Series(atr, index=ohlcv.index)
