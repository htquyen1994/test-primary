"""
RSI — Relative Strength Index
==============================
N-period RSI using Wilder smoothing (Wilder's original method).
Returns NaN for indices 0..N-1.

Satisfies: Requirements 4.2, 4.4, 4.5
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator


class RSI(BaseIndicator):
    """
    Relative Strength Index (Wilder smoothing).

    RSI = 100 - 100 / (1 + RS)
    RS  = avg_gain / avg_loss  (Wilder EMA)

    First valid value is at index N (requires N+1 candles for first diff).
    Indices 0..N-1 return NaN.
    """

    def compute(self, ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Args:
            ohlcv: DataFrame with [open, high, low, close, volume]
            period: RSI period (default 14)

        Returns:
            pd.Series of RSI values [0, 100], NaN for 0..period-1
        """
        self._validate_ohlcv(ohlcv)
        n = len(ohlcv)

        if n == 0:
            return pd.Series(dtype=float)

        close = ohlcv["close"].values.astype(float)
        rsi = np.full(n, np.nan)

        if n <= period:
            return pd.Series(rsi, index=ohlcv.index)

        # Price changes
        delta = np.diff(close)  # length n-1

        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)

        # Seed: simple average of first `period` gains/losses
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # First RSI value at index `period`
        if avg_loss == 0:
            rsi[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[period] = 100.0 - 100.0 / (1.0 + rs)

        # Wilder smoothing for subsequent values
        alpha = 1.0 / period
        for i in range(period + 1, n):
            avg_gain = avg_gain * (1 - alpha) + gains[i - 1] * alpha
            avg_loss = avg_loss * (1 - alpha) + losses[i - 1] * alpha
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100.0 - 100.0 / (1.0 + rs)

        return pd.Series(rsi, index=ohlcv.index)
