"""
Walk-Forward Analysis
======================
Partitions historical data into sequential in-sample / out-of-sample windows.
Validates that strategy parameters generalize beyond the training window.

Satisfies: Requirements 10.1–10.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from backtest.engine import BacktestingEngine
from backtest.metrics import compute_metrics, write_result_record
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

DEFAULT_OVERFIT_THRESHOLD = 0.20  # 20% degradation flags as overfit


@dataclass
class WalkForwardWindow:
    """One in-sample / out-of-sample window pair."""
    window_index: int
    in_sample_start: int
    in_sample_end: int
    out_sample_start: int
    out_sample_end: int
    in_sample_metrics: dict = field(default_factory=dict)
    out_sample_metrics: dict = field(default_factory=dict)
    is_overfit: bool = False


class WalkForwardAnalysis:
    """
    Runs walk-forward analysis over historical OHLCV data.

    Satisfies: Requirements 10.1–10.5
    """

    def __init__(
        self,
        in_sample_days: int = 90,
        out_sample_days: int = 30,
        step_days: int = 30,
        candles_per_day: int = 96,  # 15m candles per day
        overfit_threshold: float = DEFAULT_OVERFIT_THRESHOLD,
    ) -> None:
        self.in_sample_days = in_sample_days
        self.out_sample_days = out_sample_days
        self.step_days = step_days
        self.candles_per_day = candles_per_day
        self.overfit_threshold = overfit_threshold

    @classmethod
    def from_config(cls, config) -> "WalkForwardAnalysis":
        wf = config.backtest.walk_forward
        return cls(
            in_sample_days=wf.in_sample_days,
            out_sample_days=wf.out_sample_days,
            step_days=wf.step_days,
            overfit_threshold=config.backtest.overfit_degradation_threshold,
        )

    def run(
        self,
        strategy: BaseStrategy,
        ohlcv: pd.DataFrame,
        engine: BacktestingEngine,
        strategy_name: str,
        asset: str,
        timeframe: str,
        log_dir: str = "logs/backtest/",
    ) -> List[WalkForwardWindow]:
        """
        Run walk-forward analysis.

        Args:
            strategy:      BaseStrategy instance
            ohlcv:         Full historical OHLCV (sorted ascending)
            engine:        BacktestingEngine instance
            strategy_name: For logging
            asset:         For logging
            timeframe:     For logging
            log_dir:       Where to write result records

        Returns:
            List of WalkForwardWindow with metrics for each window

        Satisfies: Requirements 10.1–10.5
        """
        ohlcv = ohlcv.sort_index()
        n = len(ohlcv)

        in_sample_candles = self.in_sample_days * self.candles_per_day
        out_sample_candles = self.out_sample_days * self.candles_per_day
        step_candles = self.step_days * self.candles_per_day
        window_size = in_sample_candles + out_sample_candles

        if n < window_size:
            logger.warning(
                "Insufficient data for walk-forward: need %d candles, have %d",
                window_size, n,
            )
            return []

        windows: List[WalkForwardWindow] = []
        window_idx = 0
        start = 0

        while start + window_size <= n:
            in_end = start + in_sample_candles
            out_end = in_end + out_sample_candles

            window = WalkForwardWindow(
                window_index=window_idx,
                in_sample_start=start,
                in_sample_end=in_end,
                out_sample_start=in_end,
                out_sample_end=out_end,
            )

            # In-sample evaluation
            in_ohlcv = ohlcv.iloc[start:in_end]
            in_trades = engine.run(strategy, in_ohlcv)
            window.in_sample_metrics = compute_metrics(in_trades)

            # Out-of-sample evaluation (Req 10.2 — evaluate on out-of-sample only)
            out_ohlcv = ohlcv.iloc[in_end:out_end]
            out_trades = engine.run(strategy, out_ohlcv)
            window.out_sample_metrics = compute_metrics(out_trades)

            # Overfit check (Req 10.5)
            window.is_overfit = self._check_overfit(
                window.in_sample_metrics,
                window.out_sample_metrics,
            )

            # Write result records
            write_result_record(
                metrics=window.in_sample_metrics,
                strategy_name=strategy_name, asset=asset, timeframe=timeframe,
                start_date=str(start), end_date=str(in_end),
                config_snapshot={}, log_dir=log_dir,
                is_walk_forward=True, wf_window_index=window_idx, is_in_sample=True,
            )
            write_result_record(
                metrics=window.out_sample_metrics,
                strategy_name=strategy_name, asset=asset, timeframe=timeframe,
                start_date=str(in_end), end_date=str(out_end),
                config_snapshot={}, log_dir=log_dir,
                is_walk_forward=True, wf_window_index=window_idx, is_in_sample=False,
            )

            if window.is_overfit:
                logger.warning(
                    "Window %d flagged as potentially overfit: "
                    "in-sample win_rate=%.2f, out-sample win_rate=%.2f",
                    window_idx,
                    window.in_sample_metrics.get("win_rate", 0),
                    window.out_sample_metrics.get("win_rate", 0),
                )

            windows.append(window)
            start += step_candles
            window_idx += 1

        logger.info(
            "Walk-forward complete: %d windows, %d flagged as overfit",
            len(windows), sum(1 for w in windows if w.is_overfit),
        )
        return windows

    def _check_overfit(self, in_metrics: dict, out_metrics: dict) -> bool:
        """
        Flag as overfit if out-of-sample performance degrades by more than
        overfit_threshold relative to in-sample.

        Satisfies: Requirement 10.5
        """
        in_wr = in_metrics.get("win_rate", 0.0)
        out_wr = out_metrics.get("win_rate", 0.0)
        if in_wr == 0:
            return False
        degradation = (in_wr - out_wr) / in_wr
        return degradation > self.overfit_threshold
