"""
BaseSignalFilter — Abstract Interface
=======================================
All signal filters must implement this interface.

A filter receives a context dict and returns a FilterResult.
If passed=False, the signal is blocked and no alert is published.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FilterResult:
    """
    Result of applying a signal filter.

    Fields:
        passed:           True = signal continues; False = signal blocked
        block_reason:     Why the signal was blocked (logged + stored)
        score_adjustment: Points to add/subtract from final score
        size_multiplier:  Position size multiplier (1.0 = no change)
        warning:          Warning message shown on Signal Card (Scenario B)
        filter_name:      Which filter produced this result
    """
    passed: bool = True
    block_reason: Optional[str] = None
    score_adjustment: float = 0.0
    size_multiplier: float = 1.0
    warning: Optional[str] = None
    filter_name: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def block(cls, reason: str, filter_name: str = "") -> "FilterResult":
        """Convenience constructor for a blocking result."""
        return cls(
            passed=False,
            block_reason=reason,
            score_adjustment=-999,
            size_multiplier=0.0,
            filter_name=filter_name,
        )

    @classmethod
    def pass_with_warning(
        cls,
        score_adjustment: float,
        size_multiplier: float,
        warning: str,
        filter_name: str = "",
    ) -> "FilterResult":
        """Convenience constructor for Scenario B (pass but warn)."""
        return cls(
            passed=True,
            score_adjustment=score_adjustment,
            size_multiplier=size_multiplier,
            warning=warning,
            filter_name=filter_name,
        )

    @classmethod
    def pass_clean(cls, score_adjustment: float = 0.0, filter_name: str = "") -> "FilterResult":
        """Convenience constructor for Scenario A (aligned, no warning)."""
        return cls(
            passed=True,
            score_adjustment=score_adjustment,
            size_multiplier=1.0,
            filter_name=filter_name,
        )

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "block_reason": self.block_reason,
            "score_adjustment": self.score_adjustment,
            "size_multiplier": self.size_multiplier,
            "warning": self.warning,
            "filter_name": self.filter_name,
        }


class BaseSignalFilter(ABC):
    """
    Abstract interface for all signal filters.

    Subclasses must:
      1. Set class attribute `name` (unique string key)
      2. Implement `apply(context: dict) -> FilterResult`

    The `context` dict contains all data available at scoring time:
      - symbol, timeframe, signal_direction
      - ohlcv, ohlcv_1h, ohlcv_4h, ohlcv_daily
      - regime_state
      - redis client (r)
      - Any other data the filter needs
    """

    name: str = ""  # Override in subclass — used as registry key

    @abstractmethod
    def apply(self, context: dict) -> FilterResult:
        """
        Apply this filter to the current signal context.

        Args:
            context: Dict with all scoring-time data. Keys include:
                symbol (str), timeframe (str), signal_direction (str),
                ohlcv (DataFrame), ohlcv_1h (DataFrame),
                ohlcv_4h (DataFrame), ohlcv_daily (DataFrame),
                regime_state (RegimeState), r (Redis client),
                delta (float), bid_stack (float), ask_stack (float),
                funding_rate (float)

        Returns:
            FilterResult — if passed=False, signal is blocked
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
