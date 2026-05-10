"""
Logging Setup Helper
=====================
Consistent log format across all services (backend, mock-exchange, etc.)

Usage:
    from trading_core.utils.logging import setup_logging
    setup_logging("INFO")
"""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger with consistent format.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
