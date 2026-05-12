"""
Signal Dataclass
=================
Discrete buy or sell recommendation produced by a Strategy at a specific candle close.
Contains all information needed to build a Signal Card and write a Signal_Log entry.

Satisfies: Requirements 5.4, 6.1, 17.2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ScoreBreakdown:
    """Per-module score breakdown for a Signal."""
    order_flow: float = 0.0   # 0–35 pts
    smc: float = 0.0          # 0–30 pts
    vsa: float = 0.0          # 0–30 pts
    context: float = 0.0      # 0–15 pts
    bonus: float = 0.0        # 0–15 pts (confluence bonus)

    def to_dict(self) -> dict:
        return {
            "order_flow": self.order_flow,
            "smc": self.smc,
            "vsa": self.vsa,
            "context": self.context,
            "bonus": self.bonus,
        }


@dataclass
class Signal:
    """
    Discrete buy or sell recommendation produced by a Strategy.

    Validation rules (enforced in __post_init__):
    - direction must be "long" or "short"
    - final_score must be in [0, 100]
    - classification must be "ALERT", "WATCH", or "IGNORE"
    - regime must be one of the four valid states

    Satisfies: Requirements 5.4, 6.1, 17.2
    """

    # --- Identity ---
    strategy_name: str
    asset: str                          # e.g. "BTC/USDT"
    timeframe: str                      # e.g. "15m"
    direction: str                      # "long" | "short"
    candle_index: int                   # index T of the closed candle
    candle_timestamp: datetime

    # --- Trade levels ---
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float

    # --- Scoring ---
    raw_score: float                    # before regime multiplier (0–125)
    final_score: int                    # [0, 100] after multiplier + normalize
    score_breakdown: ScoreBreakdown
    classification: str                 # "ALERT" | "WATCH" | "IGNORE"

    # --- Market context ---
    regime: str                         # "TRENDING" | "RANGING" | "PARABOLIC" | "CHOPPY"
    regime_multiplier: float
    funding_rate: float
    portfolio_heat: float
    correlated_group_risk: float

    # --- Time invalidation ---
    expires_at_candle: int              # candle index after which signal expires

    # --- Optional / mutable ---
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_action: Optional[str] = None   # "CONFIRM" | "SKIP" | "EXPIRED" | "IGNORE"
    skip_reason: Optional[str] = None
    expiry_price: Optional[float] = None

    # --- Validation ---
    _VALID_DIRECTIONS = frozenset({"long", "short"})
    _VALID_CLASSIFICATIONS = frozenset({"ALERT", "WATCH", "IGNORE"})
    _VALID_REGIMES = frozenset({"TRENDING", "RANGING", "PARABOLIC", "CHOPPY"})
    _VALID_USER_ACTIONS = frozenset({"CONFIRM", "SKIP", "EXPIRED", "IGNORE", None})

    def __post_init__(self) -> None:
        if self.direction not in self._VALID_DIRECTIONS:
            raise ValueError(
                f"Signal.direction must be one of {self._VALID_DIRECTIONS}, "
                f"got '{self.direction}'"
            )
        if not (0 <= self.final_score <= 100):
            raise ValueError(
                f"Signal.final_score must be in [0, 100], got {self.final_score}"
            )
        if self.classification not in self._VALID_CLASSIFICATIONS:
            raise ValueError(
                f"Signal.classification must be one of {self._VALID_CLASSIFICATIONS}, "
                f"got '{self.classification}'"
            )
        if self.regime not in self._VALID_REGIMES:
            raise ValueError(
                f"Signal.regime must be one of {self._VALID_REGIMES}, "
                f"got '{self.regime}'"
            )

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON logging (Signal_Log schema)."""
        return {
            "strategy_name": self.strategy_name,
            "asset": self.asset,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "candle_index": self.candle_index,
            "candle_timestamp": self.candle_timestamp.isoformat(),
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "raw_score": self.raw_score,
            "final_score": self.final_score,
            "score_breakdown": self.score_breakdown.to_dict(),
            "classification": self.classification,
            "regime": self.regime,
            "regime_multiplier": self.regime_multiplier,
            "funding_rate": self.funding_rate,
            "portfolio_heat": self.portfolio_heat,
            "correlated_group_risk": self.correlated_group_risk,
            "expires_at_candle": self.expires_at_candle,
            "created_at": self.created_at.isoformat(),
            "user_action": self.user_action,
            "skip_reason": self.skip_reason,
            "expiry_price": self.expiry_price,
        }

    @property
    def gross_rr(self) -> float:
        """Gross Risk:Reward ratio to TP1."""
        sl_dist = abs(self.entry_price - self.stop_loss)
        if sl_dist == 0:
            return 0.0
        return abs(self.take_profit_1 - self.entry_price) / sl_dist

    def __repr__(self) -> str:
        return (
            f"<Signal {self.strategy_name} | {self.asset} {self.direction} "
            f"score={self.final_score} {self.classification} "
            f"entry={self.entry_price:.2f}>"
        )
