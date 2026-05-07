"""
Base Indicator
==============
Abstract base class for all technical indicators.
Enforces the no-look-ahead constraint at the interface level.

Satisfies: Requirements 4.1, 4.3, 4.4, 5.1
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Union

import numpy as np
import pandas as pd


class LookAheadError(RuntimeError):
    """
    Raised when a strategy or indicator accesses future candle data.
    Satisfies: Requirement 5.3
    """
    def __init__(self, source: str, offending_index: int, max_allowed: int) -> None:
        super().__init__(
            f"Look-ahead bias detected in '{source}': "
            f"accessed index {offending_index} but only indices 0..{max_allowed} are allowed. "
            f"This would cause inflated backtest results."
        )
        self.source = source
        self.offending_index = offending_index
        self.max_allowed = max_allowed


class BaseIndicator(ABC):
    """
    Abstract base for all indicator functions.

    Contract:
    - compute() accepts a DataFrame of CLOSED candles and a period N
    - Returns an array of the same length as the input
    - Positions 0..N-2 MUST return NaN (insufficient data)
    - MUST NOT access any candle beyond the last row of the input (no look-ahead)

    Satisfies: Requirements 4.1, 4.3, 4.4, 12.3
    """

    @abstractmethod
    def compute(
        self,
        ohlcv: pd.DataFrame,
        period: int,
    ) -> Union[np.ndarray, pd.Series]:
        """
        Compute indicator values from OHLCV data.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume],
                   indexed by timestamp in ascending order.
                   Contains ONLY closed candles (index 0..T).
            period: Lookback period N.

        Returns:
            Array of same length as ohlcv.
            Indices 0..N-2 MUST be NaN (Req 4.5).
            Index T value MUST equal compute(ohlcv[:T+1], period)[T] for all T (Req 4.3).

        Raises:
            LookAheadError: if implementation accesses future data (Req 5.3).
        """
        ...

    # ------------------------------------------------------------------
    # Shared utilities available to all subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_ohlcv(ohlcv: pd.DataFrame) -> None:
        """Ensure required columns are present."""
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(ohlcv.columns)
        if missing:
            raise ValueError(f"OHLCV DataFrame missing columns: {missing}")

    @staticmethod
    def _nan_array(length: int) -> np.ndarray:
        """Return an array of NaN values of the given length."""
        arr = np.empty(length)
        arr[:] = np.nan
        return arr

    @staticmethod
    def assert_no_lookahead(ohlcv: pd.DataFrame, T: int, source: str = "indicator") -> None:
        """
        Assert that the DataFrame does not contain candles beyond index T.
        Call this at the start of compute() when T is known.

        Satisfies: Requirement 4.3, 5.1
        """
        if len(ohlcv) > T + 1:
            raise LookAheadError(source, T + 1, T)
