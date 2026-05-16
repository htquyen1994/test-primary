"""
Config Check — SQL Server
==========================
Check trading_params, exchange_settings, exchange_assets.
Run: python check_config.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from _db import get_connection
from sqlalchemy import text

with get_connection() as conn:

    print("=" * 68)
    print("ACTIVE TRADING PARAMS")
    print("=" * 68)
    cols = conn.execute(text(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME='trading_params' ORDER BY ORDINAL_POSITION"
    )).fetchall()
    col_names = [c[0] for c in cols]
    rows = conn.execute(text("SELECT * FROM trading_params WHERE is_active = 1")).fetchall()
    if rows:
        for r in rows:
            for k, v in zip(col_names, r):
                print(f"  {k:<35}: {v}")
    else:
        print("  No active trading_params!")

    print("\n" + "=" * 68)
    print("ACTIVE EXCHANGE SETTINGS")
    print("=" * 68)
    cols2 = conn.execute(text(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME='exchange_settings' ORDER BY ORDINAL_POSITION"
    )).fetchall()
    col_names2 = [c[0] for c in cols2]
    rows2 = conn.execute(text("SELECT * FROM exchange_settings WHERE is_active = 1")).fetchall()
    if rows2:
        for r in rows2:
            for k, v in zip(col_names2, r):
                if any(x in k.lower() for x in ['secret', 'api_key', 'password', 'encrypted']):
                    print(f"  {k:<35}: ***MASKED***")
                else:
                    print(f"  {k:<35}: {v}")
    else:
        print("  No active exchange_settings!")

    print("\n" + "=" * 68)
    print("EXCHANGE ASSETS")
    print("=" * 68)
    rows3 = conn.execute(text("SELECT symbol, enabled, leverage_override FROM exchange_assets")).fetchall()
    if rows3:
        for r in rows3:
            print(f"  {r.symbol:<16} enabled={r.enabled} leverage={r.leverage_override}")
    else:
        print("  No assets configured!")

    print("\n" + "=" * 68)
    print("TRADING PARAMS VERSION HISTORY")
    print("=" * 68)
    rows4 = conn.execute(text(
        "SELECT version_tag, is_active, created_at, trigger_timeframe, "
        "score_alert_threshold, score_watch_threshold "
        "FROM trading_params ORDER BY created_at DESC"
    )).fetchall()
    print(f"  {'Version':<25} {'Active':>7} {'Trigger TF':>11} {'Alert':>6} {'Watch':>6} {'Created'}")
    print(f"  {'-'*25} {'-'*7} {'-'*11} {'-'*6} {'-'*6} {'-'*20}")
    for r in rows4:
        active = "ACTIVE" if r.is_active else "      "
        print(f"  {r.version_tag:<25} {active:>7} {r.trigger_timeframe:>11} {r.score_alert_threshold:>6} {r.score_watch_threshold:>6}  {r.created_at}")
