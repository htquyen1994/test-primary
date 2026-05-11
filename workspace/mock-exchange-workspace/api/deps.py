"""
FastAPI dependency injection.
Provides shared instances (MockExchange, auditors, etc.) to route handlers.
"""

from __future__ import annotations

from typing import Optional

# These are set by main.py after startup
_mock_exchange = None
_signal_auditor = None
_trade_auditor = None
_no_signal_auditor = None
_analysis_engine = None
_ws_manager = None


def set_dependencies(
    mock_exchange,
    signal_auditor,
    trade_auditor,
    no_signal_auditor,
    analysis_engine,
    ws_manager,
) -> None:
    global _mock_exchange, _signal_auditor, _trade_auditor
    global _no_signal_auditor, _analysis_engine, _ws_manager
    _mock_exchange = mock_exchange
    _signal_auditor = signal_auditor
    _trade_auditor = trade_auditor
    _no_signal_auditor = no_signal_auditor
    _analysis_engine = analysis_engine
    _ws_manager = ws_manager


def get_mock_exchange():
    return _mock_exchange


def get_signal_auditor():
    return _signal_auditor


def get_trade_auditor():
    return _trade_auditor


def get_no_signal_auditor():
    return _no_signal_auditor


def get_analysis_engine():
    return _analysis_engine


def get_ws_manager():
    return _ws_manager
