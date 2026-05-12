"""
Correlation Manager and Portfolio Heat
========================================
Computes rolling 24h Pearson correlation between all active asset pairs.
Enforces correlated-risk limits and portfolio heat limits.

Key concepts:
  - Correlation_Matrix: rolling 24h Pearson correlation between asset pairs
  - Correlated_Group: assets with pairwise correlation > threshold (default 0.8)
  - Correlated_Risk_Limit: max combined risk for a correlated group (default 3%)
  - Portfolio_Heat: sum of all open position risk percentages (default limit 6%)

Satisfies: Requirements 14.1–14.9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Defaults (all configurable via config.yaml)
DEFAULT_CORRELATION_THRESHOLD = 0.8
DEFAULT_CORRELATED_RISK_LIMIT = 3.0   # % of account equity
DEFAULT_PORTFOLIO_HEAT_LIMIT = 6.0    # % of account equity
DEFAULT_LOOKBACK_HOURS = 24


@dataclass
class CorrelationCheckResult:
    """Result of a correlated-risk check for a new signal."""
    allowed: bool
    rejection_reason: str = ""
    correlated_group: List[str] = field(default_factory=list)
    group_risk_pct: float = 0.0
    portfolio_heat: float = 0.0


class CorrelationManager:
    """
    Manages rolling correlations between assets and enforces risk limits.

    Usage:
        manager = CorrelationManager(config)
        manager.update("BTC/USDT", ohlcv_1h_btc)
        manager.update("ETH/USDT", ohlcv_1h_eth)

        result = manager.check_new_signal(
            asset="SOL/USDT",
            new_risk_pct=0.02,
            open_positions={"BTC/USDT": 0.02, "ETH/USDT": 0.015},
        )

    Satisfies: Requirements 14.1–14.9
    """

    def __init__(
        self,
        correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
        max_correlated_risk_pct: float = DEFAULT_CORRELATED_RISK_LIMIT,
        portfolio_heat_limit_pct: float = DEFAULT_PORTFOLIO_HEAT_LIMIT,
        lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    ) -> None:
        self.correlation_threshold = correlation_threshold
        self.max_correlated_risk_pct = max_correlated_risk_pct
        self.portfolio_heat_limit_pct = portfolio_heat_limit_pct
        self.lookback_hours = lookback_hours

        # Internal state: {asset: pd.Series of close prices}
        self._close_series: Dict[str, pd.Series] = {}
        # Cached correlation matrix (updated on each 1h candle close)
        self._correlation_matrix: Optional[pd.DataFrame] = None

    @classmethod
    def from_config(cls, config) -> "CorrelationManager":
        """Create from validated AppConfig."""
        r = config.risk
        return cls(
            correlation_threshold=r.correlation_threshold,
            max_correlated_risk_pct=r.max_correlated_risk_pct,
            portfolio_heat_limit_pct=r.portfolio_heat_limit_pct,
        )

    # ------------------------------------------------------------------
    # Data update
    # ------------------------------------------------------------------

    def update(self, asset: str, ohlcv_1h: pd.DataFrame) -> None:
        """
        Update the close price series for an asset.
        Call this at each 1h candle close.

        Satisfies: Requirement 14.2
        """
        if ohlcv_1h.empty:
            return

        closes = ohlcv_1h["close"].astype(float)
        # Keep only the last lookback_hours candles
        self._close_series[asset] = closes.iloc[-self.lookback_hours:]
        # Invalidate cached matrix
        self._correlation_matrix = None

    # ------------------------------------------------------------------
    # Correlation matrix
    # ------------------------------------------------------------------

    def get_correlation_matrix(self) -> pd.DataFrame:
        """
        Compute (or return cached) rolling 24h Pearson correlation matrix.

        Returns:
            DataFrame with assets as both index and columns.
            Values are Pearson correlation coefficients in [-1.0, 1.0].

        Satisfies: Requirements 14.1, 14.2
        """
        if self._correlation_matrix is not None:
            return self._correlation_matrix

        if len(self._close_series) < 2:
            return pd.DataFrame()

        # Align all series to the same index
        df = pd.DataFrame(self._close_series)
        df = df.dropna()

        if df.empty or len(df) < 2:
            return pd.DataFrame()

        # Use log returns instead of raw prices to avoid spurious correlations
        # from shared price levels (e.g. all assets rising together in a bull market)
        log_returns = np.log(df / df.shift(1)).dropna()
        if log_returns.empty or len(log_returns) < 2:
            self._correlation_matrix = pd.DataFrame()
            return self._correlation_matrix
        self._correlation_matrix = log_returns.corr(method="pearson")
        return self._correlation_matrix

    def get_correlated_group(
        self,
        asset: str,
        open_positions: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """
        Return all assets whose correlation with `asset` exceeds the threshold.
        Optionally filter to only assets with open positions.

        Satisfies: Requirement 14.3
        """
        matrix = self.get_correlation_matrix()
        if matrix.empty or asset not in matrix.columns:
            return []

        correlated = [
            other for other in matrix.columns
            if other != asset and
            abs(matrix.loc[asset, other]) > self.correlation_threshold
        ]

        if open_positions is not None:
            correlated = [a for a in correlated if a in open_positions]

        return correlated

    # ------------------------------------------------------------------
    # Portfolio Heat
    # ------------------------------------------------------------------

    def get_portfolio_heat(self, open_positions: Dict[str, float]) -> float:
        """
        Compute Portfolio_Heat = sum of all open position risk percentages.

        Args:
            open_positions: {asset: risk_pct_of_equity}
                            e.g. {"BTC/USDT": 0.02, "ETH/USDT": 0.015}

        Returns:
            Total portfolio heat as a percentage (e.g. 3.5 for 3.5%)

        Satisfies: Requirement 14.6
        """
        return sum(open_positions.values()) * 100.0  # convert to percentage

    # ------------------------------------------------------------------
    # Risk check
    # ------------------------------------------------------------------

    def check_new_signal(
        self,
        asset: str,
        new_risk_pct: float,
        open_positions: Dict[str, float],
    ) -> CorrelationCheckResult:
        """
        Validate a new signal against correlated-risk and portfolio-heat limits.

        Args:
            asset:          Asset symbol for the new signal
            new_risk_pct:   Risk percentage for the new position (e.g. 0.02 = 2%)
            open_positions: {asset: risk_pct} for all currently open positions

        Returns:
            CorrelationCheckResult with allowed=True/False and rejection reason

        Satisfies: Requirements 14.3–14.7
        """
        # --- Portfolio Heat check (Req 14.7) ---
        current_heat = self.get_portfolio_heat(open_positions)
        new_heat = current_heat + new_risk_pct * 100.0

        if new_heat > self.portfolio_heat_limit_pct:
            return CorrelationCheckResult(
                allowed=False,
                rejection_reason=(
                    f"Portfolio_Heat {current_heat:.2f}% + {new_risk_pct*100:.2f}% "
                    f"= {new_heat:.2f}% exceeds limit {self.portfolio_heat_limit_pct:.2f}%"
                ),
                portfolio_heat=current_heat,
            )

        # --- Correlated group risk check (Req 14.3–14.5) ---
        correlated = self.get_correlated_group(asset, open_positions)
        group_risk_pct = new_risk_pct * 100.0 + sum(
            open_positions.get(a, 0.0) * 100.0 for a in correlated
        )

        if group_risk_pct > self.max_correlated_risk_pct:
            return CorrelationCheckResult(
                allowed=False,
                rejection_reason=(
                    f"Correlated group {[asset] + correlated} combined risk "
                    f"{group_risk_pct:.2f}% exceeds limit {self.max_correlated_risk_pct:.2f}%. "
                    f"Members: {correlated}"
                ),
                correlated_group=correlated,
                group_risk_pct=group_risk_pct,
                portfolio_heat=current_heat,
            )

        return CorrelationCheckResult(
            allowed=True,
            correlated_group=correlated,
            group_risk_pct=group_risk_pct,
            portfolio_heat=current_heat,
        )
