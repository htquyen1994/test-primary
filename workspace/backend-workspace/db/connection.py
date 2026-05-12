"""
Database Connection — Re-export from trading_core
===================================================
This module now delegates to trading_core.db for the engine factory.
Kept for backward compatibility with existing imports in this workspace.

All new code should import directly from trading_core:
    from trading_core.db import get_engine, get_session_factory, get_session, Base
"""

from trading_core.db import get_engine, get_session_factory, get_session, Base

__all__ = ["get_engine", "get_session_factory", "get_session", "Base"]
