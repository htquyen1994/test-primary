"""
Backtest Models
================
TradeResult dataclass for simulated and live trades.

Satisfies: Requirements 8, 9, 19
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TradeResult:
    """
    Result of a single simulated or live trade.

    Satisfies: Requirements 8, 9, 19
    """
    # Identity
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = ""
    asset: str = ""
    timeframe: str = "15m"
    direction: str = "long"             # "long" | "short"

    # Timestamps
    entry_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_timestamp: Optional[datetime] = None

    # Prices (planned)
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0

    # Prices (actual — after slippage)
    actual_entry_price: float = 0.0
    actual_exit_price: Optional[float] = None

    # Position
    position_size_usd: float = 0.0
    leverage: int = 1

    # Costs
    slippage_entry: float = 0.0         # actual_entry - entry_price
    slippage_exit: float = 0.0
    fee_entry: float = 0.0
    fee_exit: float = 0.0
    funding_paid: float = 0.0           # total funding rate payments during hold

    # PnL
    gross_pnl: float = 0.0             # before fees/slippage
    net_pnl: float = 0.0               # gross - fees - slippage - funding

    # Result
    result: str = ""                    # "win" | "loss" | "be"
    signal_score: int = 0

    # Metadata
    exchange_order_id: Optional[str] = None
    is_testnet: bool = True

    def __post_init__(self) -> None:
        if self.direction not in ("long", "short"):
            raise ValueError(f"direction must be 'long' or 'short', got '{self.direction}'")
        if self.result and self.result not in ("win", "loss", "be"):
            raise ValueError(f"result must be 'win', 'loss', or 'be', got '{self.result}'")

    def compute_result(self) -> None:
        """Set result based on net_pnl."""
        if self.net_pnl > 0:
            self.result = "win"
        elif self.net_pnl < 0:
            self.result = "loss"
        else:
            self.result = "be"
