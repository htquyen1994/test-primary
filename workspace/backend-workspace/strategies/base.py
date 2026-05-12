"""
BaseStrategy Abstract Class
============================
Every strategy must implement this interface.
Enforces no-look-ahead constraint at the interface level.

Satisfies: Requirements 12.2, 16.1, 5.1, 5.3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import pandas as pd

from indicators.base import LookAheadError
from strategies.signal import Signal


class BaseStrategy(ABC):
    """
    Abstract interface every Strategy class must implement.

    Contract:
    - generate_signals() receives ONLY closed candles (index 0..T)
    - MUST NOT access any candle beyond the last row of ohlcv
    - Returns a list of Signal objects (empty list if no signal)
    - name property returns the unique strategy identifier

    Satisfies: Requirements 12.2, 16.1, 5.1, 5.3
    """

    def __init__(self, config: dict) -> None:
        """
        Args:
            config: Validated AppConfig object from ConfigSystem.
                    All strategy parameters are sourced from here (Req 16.7).
        """
        self.config = config

    @abstractmethod
    def generate_signals(
        self,
        ohlcv: pd.DataFrame,
        context: dict,
    ) -> List[Signal]:
        """
        Generate signals from closed candle data.

        Args:
            ohlcv: DataFrame of CLOSED candles only (index 0..T).
                   Columns: [open, high, low, close, volume]
                   MUST NOT contain any candle that has not yet closed (Req 5.2).

            context: Dict containing:
                - "ohlcv_1h": pd.DataFrame — higher timeframe candles for bias
                - "regime": str — current regime state
                - "regime_multiplier": float
                - "funding_rate": float
                - "portfolio_heat": float
                - "correlated_group_risk": float
                - "delta": float — cumulative order flow delta
                - "bid_stack": float — bid stack size at S/R
                - "ask_stack": float — ask stack size at S/R
                - "poc": float — Point of Control from Volume Profile
                - "vah": float — Value Area High
                - "val": float — Value Area Low

        Returns:
            List of Signal objects. Empty list if no signal detected.

        Constraint: SHALL only access ohlcv.iloc[:T+1] — no future data (Req 5.1).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique strategy identifier used in Strategy_Registry.
        Must match the name used in @register() decorator.
        """
        ...

    # ------------------------------------------------------------------
    # Shared guard — call at start of generate_signals()
    # ------------------------------------------------------------------

    def _check_no_lookahead(self, ohlcv: pd.DataFrame, T: int) -> None:
        """
        Assert that ohlcv does not contain candles beyond index T.
        Raises LookAheadError if violated.

        Usage:
            def generate_signals(self, ohlcv, context):
                T = len(ohlcv) - 1
                self._check_no_lookahead(ohlcv, T)
                ...

        Satisfies: Requirements 5.1, 5.3
        """
        if len(ohlcv) > T + 1:
            raise LookAheadError(
                source=self.name,
                offending_index=T + 1,
                max_allowed=T,
            )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @property
    def score_threshold_alert(self) -> int:
        """Alert threshold from config (default 75)."""
        try:
            return self.config.strategy.score_threshold.alert
        except AttributeError:
            return 75

    @property
    def score_threshold_watch(self) -> int:
        """Watch threshold from config (default 55)."""
        try:
            return self.config.strategy.score_threshold.watch
        except AttributeError:
            return 55

    @property
    def time_invalidation_candles(self) -> int:
        """Number of candles before a signal expires (default 15)."""
        try:
            return self.config.strategy.time_invalidation_candles
        except AttributeError:
            return 15

    def classify_score(self, score: int) -> str:
        """Classify a final score into ALERT / WATCH / IGNORE."""
        if score >= self.score_threshold_alert:
            return "ALERT"
        elif score >= self.score_threshold_watch:
            return "WATCH"
        return "IGNORE"
