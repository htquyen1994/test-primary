"""
Signal Filter Pipeline
=======================
Plugin-based filter system for signal scoring pipeline.

Filters run BEFORE scoring and can:
  - Block a signal completely (passed=False)
  - Adjust score (+/- pts)
  - Adjust position size multiplier
  - Add warning messages to Signal Card

On/off via config (DB or config.yaml):
    filters:
      active:
        - mtf_bias
        - btc_guard
        - circuit_breaker
        # comment out to disable

Usage:
    from engine.filters import FilterRegistry, FilterResult

    # Load active filters from config
    active = FilterRegistry.load_active(["mtf_bias", "btc_guard"])

    # Apply in pipeline
    for f in active:
        result = f.apply(context)
        if not result.passed:
            return  # block signal
        size_mult *= result.size_multiplier
        score += result.score_adjustment
"""

from engine.filters.base import BaseSignalFilter, FilterResult
from engine.filters.registry import FilterRegistry

__all__ = ["BaseSignalFilter", "FilterResult", "FilterRegistry"]
