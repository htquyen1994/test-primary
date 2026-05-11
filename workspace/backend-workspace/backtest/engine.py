"""
Backtesting Engine — Trade Simulation
=======================================
Simulates realistic trade execution against historical OHLCV data.

Key constraints (Req 5.1, 8.6):
  - Processes candles in strictly ascending timestamp order
  - Passes only ohlcv[:T+1] to strategy.generate_signals() — no look-ahead
  - Applies slippage to fill prices
  - Deducts fees per trade
  - Applies funding rate payments during hold period
  - Intra-candle SL/TP fill (checks if SL/TP was hit within the candle)

Satisfies: Requirements 8.1–8.6
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from backtest.models import TradeResult
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

# Default costs
DEFAULT_FUTURES_FEE = 0.0004    # 0.04% per fill
DEFAULT_SPOT_FEE = 0.001        # 0.1% per fill
DEFAULT_SLIPPAGE = 0.0005       # 0.05%
FUNDING_INTERVAL_HOURS = 8      # funding paid every 8h


class BacktestingEngine:
    """
    Simulates trade execution against historical OHLCV data.

    Satisfies: Requirements 8.1–8.6
    """

    def __init__(
        self,
        fee_rate: float = DEFAULT_FUTURES_FEE,
        slippage_pct: float = DEFAULT_SLIPPAGE,
        market_type: str = "futures",
        initial_equity: float = 10000.0,
    ) -> None:
        self.fee_rate = fee_rate
        self.slippage_pct = slippage_pct
        self.market_type = market_type
        self.initial_equity = initial_equity

    @classmethod
    def from_config(cls, config) -> "BacktestingEngine":
        e = config.exchange
        return cls(
            fee_rate=e.fee_rate,
            slippage_pct=e.slippage_pct,
            market_type=e.market_type,
            initial_equity=config.account.balance,
        )

    def run(
        self,
        strategy: BaseStrategy,
        ohlcv: pd.DataFrame,
        funding_rates: Optional[pd.DataFrame] = None,
        context_builder=None,
    ) -> List[TradeResult]:
        """
        Run backtest for a single strategy over historical OHLCV data.

        Args:
            strategy:        BaseStrategy instance
            ohlcv:           Full historical OHLCV DataFrame (sorted ascending)
            funding_rates:   Optional DataFrame with funding rate history
            context_builder: Optional callable(ohlcv_slice) → context dict

        Returns:
            List of TradeResult objects

        Satisfies: Requirements 8.1–8.6
        """
        # Sort ascending — enforce chronological order (Req 8.6)
        ohlcv = ohlcv.sort_index()

        # Derive candle duration so funding interval is correct for any timeframe.
        # FUNDING_INTERVAL_HOURS=8 means 8h / candle_duration = N candles per payment.
        try:
            _tf_seconds = (ohlcv.index[1] - ohlcv.index[0]).total_seconds()
            self._timeframe_minutes = max(1, int(_tf_seconds / 60))
        except Exception:
            self._timeframe_minutes = 15  # safe default

        results: List[TradeResult] = []
        open_trade: Optional[TradeResult] = None
        equity = self.initial_equity

        for T in range(1, len(ohlcv)):
            # Pass only closed candles 0..T (no look-ahead — Req 5.1, 8.6)
            ohlcv_slice = ohlcv.iloc[:T + 1]
            current_candle = ohlcv.iloc[T]

            # --- Check if open trade hits SL or TP (intra-candle fill — Req 8.5) ---
            if open_trade is not None:
                closed = self._check_exit(open_trade, current_candle, funding_rates, T)
                if closed:
                    equity += closed.net_pnl
                    results.append(closed)
                    open_trade = None
                    continue

            # --- Generate signals (only if no open trade) ---
            if open_trade is None:
                context = context_builder(ohlcv_slice) if context_builder else {}
                try:
                    signals = strategy.generate_signals(ohlcv_slice, context)
                except Exception as exc:
                    logger.debug("Strategy error at T=%d: %s", T, exc)
                    continue

                for signal in signals:
                    if signal.classification not in ("ALERT", "WATCH"):
                        continue

                    # Simulate entry fill with slippage (Req 8.2)
                    actual_entry = self._apply_slippage(
                        signal.entry_price, signal.direction, "entry"
                    )
                    fee_entry = actual_entry * signal.position_size_usd / actual_entry * self.fee_rate \
                        if hasattr(signal, "position_size_usd") else actual_entry * 100 * self.fee_rate

                    open_trade = TradeResult(
                        strategy_name=strategy.name,
                        asset=signal.asset,
                        timeframe=signal.timeframe,
                        direction=signal.direction,
                        entry_timestamp=datetime.now(timezone.utc),
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit_1=signal.take_profit_1,
                        take_profit_2=signal.take_profit_2,
                        actual_entry_price=actual_entry,
                        slippage_entry=actual_entry - signal.entry_price,
                        fee_entry=fee_entry,
                        position_size_usd=100.0,  # simplified; use RiskManager in production
                        signal_score=signal.final_score,
                        is_testnet=True,
                    )
                    break  # one trade at a time

        # Close any remaining open trade at last candle
        if open_trade is not None:
            last_candle = ohlcv.iloc[-1]
            exit_price = float(last_candle["close"])
            self._fill_exit(open_trade, exit_price, "end_of_data")
            results.append(open_trade)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_slippage(
        self,
        price: float,
        direction: str,
        fill_type: str,
    ) -> float:
        """
        Apply slippage to a fill price.

        Long entry:  buy higher  → price × (1 + slippage)
        Short entry: sell lower  → price × (1 - slippage)
        Long exit:   sell lower  → price × (1 - slippage)
        Short exit:  buy higher  → price × (1 + slippage)

        Satisfies: Requirement 8.2
        """
        if (direction == "long" and fill_type == "entry") or \
           (direction == "short" and fill_type == "exit"):
            return price * (1 + self.slippage_pct)
        else:
            return price * (1 - self.slippage_pct)

    def _check_exit(
        self,
        trade: TradeResult,
        candle,
        funding_rates,
        candle_idx: int,
    ) -> Optional[TradeResult]:
        """
        Check if SL or TP was hit within the current candle (intra-candle fill).
        Returns closed TradeResult or None if still open.

        Satisfies: Requirement 8.5
        """
        high = float(candle["high"])
        low = float(candle["low"])

        if trade.direction == "long":
            # SL hit: candle low <= stop_loss
            if low <= trade.stop_loss:
                exit_price = self._apply_slippage(trade.stop_loss, "long", "exit")
                self._fill_exit(trade, exit_price, "sl")
                return trade
            # TP1 hit: candle high >= take_profit_1
            if high >= trade.take_profit_1:
                exit_price = self._apply_slippage(trade.take_profit_1, "long", "exit")
                self._fill_exit(trade, exit_price, "tp1")
                return trade
        else:  # short
            # SL hit: candle high >= stop_loss
            if high >= trade.stop_loss:
                exit_price = self._apply_slippage(trade.stop_loss, "short", "exit")
                self._fill_exit(trade, exit_price, "sl")
                return trade
            # TP1 hit: candle low <= take_profit_1
            if low <= trade.take_profit_1:
                exit_price = self._apply_slippage(trade.take_profit_1, "short", "exit")
                self._fill_exit(trade, exit_price, "tp1")
                return trade

        # Apply funding rate if applicable
        if funding_rates is not None and self.market_type == "futures":
            funding = self._get_funding_payment(trade, candle_idx, funding_rates)
            trade.funding_paid += funding

        return None

    def _fill_exit(self, trade: TradeResult, exit_price: float, reason: str) -> None:
        """Fill the exit and compute PnL."""
        trade.actual_exit_price = exit_price
        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.now(timezone.utc)
        trade.slippage_exit = exit_price - (trade.take_profit_1 if reason == "tp1" else trade.stop_loss)

        # Fee on exit
        trade.fee_exit = exit_price * self.fee_rate

        # Gross PnL
        if trade.direction == "long":
            trade.gross_pnl = (exit_price - trade.actual_entry_price) * (trade.position_size_usd / trade.actual_entry_price)
        else:
            trade.gross_pnl = (trade.actual_entry_price - exit_price) * (trade.position_size_usd / trade.actual_entry_price)

        # Net PnL = gross - fees - funding
        total_fees = trade.fee_entry + trade.fee_exit
        trade.net_pnl = trade.gross_pnl - total_fees - trade.funding_paid
        trade.compute_result()

    def _get_funding_payment(
        self,
        trade: TradeResult,
        candle_idx: int,
        funding_rates: pd.DataFrame,
    ) -> float:
        """Simplified funding rate payment calculation."""
        if funding_rates.empty:
            return 0.0
        # Convert 8h funding interval to candle count based on actual timeframe
        _tf_min = getattr(self, "_timeframe_minutes", 15)
        _funding_candles = max(1, int((FUNDING_INTERVAL_HOURS * 60) / _tf_min))
        if candle_idx % _funding_candles == 0:
            rate = float(funding_rates.iloc[min(candle_idx, len(funding_rates) - 1)].get("rate", 0.0))
            return abs(rate) * trade.position_size_usd
        return 0.0
