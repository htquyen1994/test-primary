"""
ADX — Average Directional Index
=================================
N-period ADX with DI+ and DI- (Wilder smoothing).
Returns NaN for indices 0..N-1.

Used by Regime Detector to classify TRENDING vs CHOPPY/RANGING.

Satisfies: Requirements 4.2, 4.4, 4.5, 13.2, 13.3
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator


@dataclass
class ADXResult:
    """Container for ADX, DI+, DI- series."""
    adx: pd.Series
    di_plus: pd.Series
    di_minus: pd.Series


class ADX(BaseIndicator):
    """
    Average Directional Index (Wilder smoothing).

    DM+ = high[i] - high[i-1]  if positive and > |low[i] - low[i-1]|, else 0
    DM- = low[i-1] - low[i]    if positive and > |high[i] - high[i-1]|, else 0
    TR  = max(high-low, |high-prev_close|, |low-prev_close|)

    Smoothed with Wilder EMA (same as ATR).
    DI+ = 100 * smoothed_DM+ / smoothed_TR
    DI- = 100 * smoothed_DM- / smoothed_TR
    DX  = 100 * |DI+ - DI-| / (DI+ + DI-)
    ADX = Wilder EMA of DX

    First valid ADX at index 2*period - 1.
    """

    def compute(self, ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Returns the ADX series only (for BaseIndicator compatibility).
        Use compute_full() to get DI+ and DI- as well.

        Returns:
            pd.Series of ADX values, NaN for 0..2*period-2
        """
        return self.compute_full(ohlcv, period).adx

    def compute_full(self, ohlcv: pd.DataFrame, period: int = 14) -> ADXResult:
        """
        Returns ADX, DI+, DI- as an ADXResult dataclass.

        Satisfies: Requirements 4.2, 4.4, 4.5
        """
        self._validate_ohlcv(ohlcv)
        n = len(ohlcv)

        adx_arr = np.full(n, np.nan)
        dip_arr = np.full(n, np.nan)
        dim_arr = np.full(n, np.nan)

        if n < period + 1:
            return ADXResult(
                adx=pd.Series(adx_arr, index=ohlcv.index),
                di_plus=pd.Series(dip_arr, index=ohlcv.index),
                di_minus=pd.Series(dim_arr, index=ohlcv.index),
            )

        high = ohlcv["high"].values.astype(float)
        low = ohlcv["low"].values.astype(float)
        close = ohlcv["close"].values.astype(float)

        # Directional movement and true range arrays
        dm_plus = np.zeros(n)
        dm_minus = np.zeros(n)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]

        for i in range(1, n):
            up_move = high[i] - high[i - 1]
            down_move = low[i - 1] - low[i]

            dm_plus[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
            dm_minus[i] = down_move if (down_move > up_move and down_move > 0) else 0.0

            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr[i] = max(hl, hc, lc)

        # Wilder smoothing
        alpha = 1.0 / period
        s_tr = np.full(n, np.nan)
        s_dmp = np.full(n, np.nan)
        s_dmm = np.full(n, np.nan)

        # Seed at index period
        s_tr[period] = np.sum(tr[1:period + 1])
        s_dmp[period] = np.sum(dm_plus[1:period + 1])
        s_dmm[period] = np.sum(dm_minus[1:period + 1])

        for i in range(period + 1, n):
            s_tr[i] = s_tr[i - 1] * (1 - alpha) + tr[i]
            s_dmp[i] = s_dmp[i - 1] * (1 - alpha) + dm_plus[i]
            s_dmm[i] = s_dmm[i - 1] * (1 - alpha) + dm_minus[i]

        # DI+ and DI-
        dx = np.full(n, np.nan)
        for i in range(period, n):
            if s_tr[i] == 0:
                continue
            dip_arr[i] = 100.0 * s_dmp[i] / s_tr[i]
            dim_arr[i] = 100.0 * s_dmm[i] / s_tr[i]
            di_sum = dip_arr[i] + dim_arr[i]
            if di_sum == 0:
                dx[i] = 0.0
            else:
                dx[i] = 100.0 * abs(dip_arr[i] - dim_arr[i]) / di_sum

        # ADX = Wilder EMA of DX, seeded at index 2*period-1
        seed_idx = 2 * period - 1
        if seed_idx < n:
            adx_arr[seed_idx] = np.nanmean(dx[period:seed_idx + 1])
            for i in range(seed_idx + 1, n):
                if not np.isnan(dx[i]):
                    adx_arr[i] = adx_arr[i - 1] * (1 - alpha) + dx[i] * alpha

        return ADXResult(
            adx=pd.Series(adx_arr, index=ohlcv.index),
            di_plus=pd.Series(dip_arr, index=ohlcv.index),
            di_minus=pd.Series(dim_arr, index=ohlcv.index),
        )
