"""
Circuit Breaker Filter
=======================
Blocks all signals when the circuit breaker is locked.

Triggers (from risk/circuit_breaker.py):
  1. 3 consecutive losses in 24h → lock 12h
  2. Single loss > 4% equity → lock 6h
  3. Daily loss > 5% → lock until 00:00 UTC
  4. Drawdown > 10% from 7-day peak → lock 24h + review

Registered as: "circuit_breaker"
"""

from __future__ import annotations

import logging

from engine.filters.base import BaseSignalFilter, FilterResult
from engine.filters.registry import FilterRegistry

logger = logging.getLogger(__name__)


@FilterRegistry.register("circuit_breaker")
class CircuitBreakerFilter(BaseSignalFilter):
    """
    Circuit Breaker Filter.
    Wraps risk.circuit_breaker logic into the filter pipeline.
    """

    name = "circuit_breaker"

    def apply(self, context: dict) -> FilterResult:
        """
        Context keys used: none (reads from Redis/DB directly)
        """
        try:
            from risk.circuit_breaker import CircuitBreaker

            cb = CircuitBreaker()
            if not cb.is_locked():
                return FilterResult.pass_clean(filter_name=self.name)

            lock_info = cb.get_lock_info()
            reason = f"CIRCUIT_BREAKER_{lock_info.trigger_type or 'LOCKED'}"
            detail = lock_info.trigger_detail or "Trading locked"

            return FilterResult.block(
                reason=reason,
                filter_name=self.name,
            )

        except Exception as exc:
            logger.warning("CircuitBreakerFilter error (non-blocking): %s", exc)
            return FilterResult.pass_clean(filter_name=self.name)
