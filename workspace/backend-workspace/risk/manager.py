"""
Risk Manager
=============
Computes position size and enforces all risk limits.

Position sizing modes:
  fixed_usd : position_size = config.position.fixed_usd
  risk_pct  : position_size = (equity * risk_pct) / (sl_distance / entry)
  kelly     : position_size = Kelly fraction × equity (based on historical win rate)

Risk limits enforced:
  - Max loss per trade ≤ equity × max_risk_pct
  - Correlated group risk ≤ max_correlated_risk_pct
  - Portfolio heat ≤ portfolio_heat_limit_pct
  - ATR = 0 → reject signal

LEVERAGE NOTE:
  position_size_usd returned here is the NOTIONAL exposure (not margin).
  For futures: notional = equity × risk_pct / SL%
  The exchange applies leverage automatically based on account leverage setting.
  margin_required = notional / leverage  (handled by exchange, not here).
  TradeExecutor converts: amount_contracts = notional / entry_price.
  Do NOT multiply by leverage here or in the executor.

Satisfies: Requirements 7.1–7.5, 14.3–14.7
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from engine.correlation_manager import CorrelationManager, CorrelationCheckResult

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_RISK_PCT = 0.02       # 2% per trade
DEFAULT_FIXED_USD = 100.0
DEFAULT_LEVERAGE = 1


@dataclass
class PositionSizeResult:
    """Result of position size calculation."""
    allowed: bool
    position_size_usd: float = 0.0
    risk_pct: float = 0.0           # actual risk as fraction of equity
    rejection_reason: str = ""
    correlation_check: Optional[CorrelationCheckResult] = None


class RiskManager:
    """
    Computes position size and enforces risk limits.

    Satisfies: Requirements 7.1–7.5, 14.3–14.7
    """

    def __init__(
        self,
        mode: str = "risk_pct",
        fixed_usd: float = DEFAULT_FIXED_USD,
        risk_pct: float = DEFAULT_MAX_RISK_PCT,
        max_risk_pct: float = DEFAULT_MAX_RISK_PCT,
        leverage: int = DEFAULT_LEVERAGE,
        market_type: str = "futures",
        correlation_manager: Optional[CorrelationManager] = None,
    ) -> None:
        self.mode = mode
        self.fixed_usd = fixed_usd
        self.risk_pct = risk_pct
        self.max_risk_pct = max_risk_pct
        self.leverage = leverage
        self.market_type = market_type
        self.correlation_manager = correlation_manager

    @classmethod
    def from_config(cls, config, correlation_manager: Optional[CorrelationManager] = None) -> "RiskManager":
        """Create from validated AppConfig."""
        p = config.position
        e = config.exchange
        return cls(
            mode=p.mode,
            fixed_usd=p.fixed_usd,
            risk_pct=p.risk_pct,
            max_risk_pct=p.risk_pct,
            leverage=p.leverage,
            market_type=e.market_type,
            correlation_manager=correlation_manager,
        )

    def compute_position_size(
        self,
        asset: str,
        entry_price: float,
        stop_loss: float,
        account_equity: float,
        atr_value: float,
        open_positions: Optional[Dict[str, float]] = None,
        fee_rate: float = 0.001,
    ) -> PositionSizeResult:
        """
        Compute position size and validate all risk limits.

        Args:
            asset:           Asset symbol (e.g. "BTC/USDT")
            entry_price:     Proposed entry price
            stop_loss:       Stop-loss price
            account_equity:  Current account equity in USD
            atr_value:       Current ATR(14) value
            open_positions:  {asset: risk_pct} for currently open positions
            fee_rate:        Exchange fee rate (default 0.1%)

        Returns:
            PositionSizeResult with allowed=True/False and position_size_usd

        Satisfies: Requirements 7.1–7.5
        """
        open_positions = open_positions or {}

        # --- ATR = 0 guard (Req 7.4) ---
        if atr_value == 0 or entry_price == 0:
            logger.warning(
                "Signal rejected: ATR=%.4f or entry_price=%.4f is zero for %s",
                atr_value, entry_price, asset,
            )
            return PositionSizeResult(
                allowed=False,
                rejection_reason=f"ATR={atr_value} or entry_price={entry_price} is zero — cannot compute position size",
            )

        sl_distance = abs(entry_price - stop_loss)
        if sl_distance == 0:
            return PositionSizeResult(
                allowed=False,
                rejection_reason="Stop-loss distance is zero",
            )

        # --- Compute raw position size by mode ---
        if self.mode == "fixed_usd":
            position_usd = self.fixed_usd
        elif self.mode == "risk_pct":
            # position_size = (equity * risk_pct) / (sl_distance / entry_price)
            sl_pct = sl_distance / entry_price
            # Include fee cost in risk budget
            fee_cost_pct = fee_rate * 2  # entry + exit
            net_risk_pct = sl_pct + fee_cost_pct
            position_usd = (account_equity * self.risk_pct) / net_risk_pct
        elif self.mode == "kelly":
            # Simplified Kelly: use risk_pct as fallback until historical data available
            sl_pct = sl_distance / entry_price
            position_usd = (account_equity * self.risk_pct) / sl_pct
        else:
            return PositionSizeResult(
                allowed=False,
                rejection_reason=f"Unknown position sizing mode: {self.mode}",
            )

        # --- Cap: max loss ≤ equity × max_risk_pct (Req 7.3) ---
        sl_pct = sl_distance / entry_price
        max_loss = account_equity * self.max_risk_pct
        max_position_from_cap = max_loss / sl_pct if sl_pct > 0 else position_usd
        position_usd = min(position_usd, max_position_from_cap)

        if position_usd <= 0:
            return PositionSizeResult(
                allowed=False,
                rejection_reason=f"Computed position size {position_usd:.2f} is zero or negative",
            )

        # Actual risk as fraction of equity
        actual_risk_pct = (position_usd * sl_pct) / account_equity

        # NOTE: No leverage multiplication here.
        # position_usd is the NOTIONAL exposure. The exchange applies leverage
        # automatically. Multiplying here would compound leverage (e.g. 10x→100x).

        # --- Correlated risk check (Req 14.3–14.7) ---
        if self.correlation_manager is not None:
            corr_result = self.correlation_manager.check_new_signal(
                asset=asset,
                new_risk_pct=actual_risk_pct,
                open_positions=open_positions,
            )
            if not corr_result.allowed:
                logger.warning(
                    "Signal rejected (correlation/heat): %s",
                    corr_result.rejection_reason,
                )
                return PositionSizeResult(
                    allowed=False,
                    rejection_reason=corr_result.rejection_reason,
                    correlation_check=corr_result,
                )

        return PositionSizeResult(
            allowed=True,
            position_size_usd=round(position_usd, 2),
            risk_pct=actual_risk_pct,
        )
