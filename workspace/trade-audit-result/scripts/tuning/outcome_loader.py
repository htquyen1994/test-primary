"""
Outcome Loader
===============
Joins signal_log (from SQL Server) with actual trade outcomes.

Outcome sources (tried in order):
  1. temp/outcomes_{date}.json   — produced by validate_signals.py --step=2
  2. Inline simulation           — fetches OHLCV via Binance public API and labels
                                   each signal as WIN / LOSS / PENDING / NO_DATA

Returns a pandas DataFrame with one row per signal:
  Columns from signal_log: log_id, timestamp, asset, timeframe, direction,
    final_score, raw_score, score_order_flow, score_smc, score_vsa,
    score_context, score_bonus, regime, regime_multiplier,
    entry_price, stop_loss, take_profit_1, classification
  Columns added by loader:
    outcome          : WIN | LOSS | PENDING | NO_DATA
    candles_to_hit   : int  (how many 5m candles to outcome)
    mae_pct          : float (max adverse excursion %)
    mfe_pct          : float (max favorable excursion %)
    rr_ratio         : float (take_profit_1 / stop_loss distance ratio)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
OUTCOME_WINDOW_CANDLES = 96          # 96 × 5m = 8 hours
PENDING_LOOKBACK_HOURS = 8           # signals < 8h old → PENDING
MIN_SIGNAL_AGE_HOURS = 8             # minimum age to attempt labeling


class OutcomeLoader:
    """
    Loads signals from DB, labels each with WIN/LOSS/PENDING/NO_DATA.
    """

    def __init__(self, conn, temp_dir: Path, lookback_days: int = 30):
        """
        Args:
            conn: open pyodbc connection (read-only usage)
            temp_dir: directory containing outcomes_*.json files
            lookback_days: how many days of signals to load
        """
        self._conn = conn
        self._temp_dir = Path(temp_dir)
        self._lookback_days = lookback_days

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self) -> pd.DataFrame:
        """
        Load signals and outcomes.
        Returns DataFrame — may be empty if no data.
        """
        signals = self._load_signals()
        if signals.empty:
            logger.info("OutcomeLoader: no signals in lookback window")
            return signals

        outcomes = self._load_outcomes_from_cache(signals)
        if outcomes:
            df = signals.copy()
            df["outcome"]        = df["log_id"].map(lambda x: outcomes.get(x, {}).get("outcome", "NO_DATA"))
            df["candles_to_hit"] = df["log_id"].map(lambda x: outcomes.get(x, {}).get("candles_to_outcome"))
            df["mae_pct"]        = df["log_id"].map(lambda x: outcomes.get(x, {}).get("max_adverse_excursion"))
            df["mfe_pct"]        = df["log_id"].map(lambda x: outcomes.get(x, {}).get("max_favorable_excursion"))
            logger.info("OutcomeLoader: loaded %d outcomes from cache", sum(1 for v in outcomes.values() if v.get("outcome") in ("WIN","LOSS")))
        else:
            logger.info("OutcomeLoader: no cache found — running inline simulation")
            df = self._simulate_outcomes(signals)

        df = self._add_rr_ratio(df)
        return df

    # ── Signal loading ──────────────────────────────────────────────────────────

    # Only simulate outcomes for signals near or above the alert threshold.
    # Rationale: labelling every IGNORE signal is prohibitively expensive (Binance API).
    # - Always include ALERT / WATCH signals (outcome validation)
    # - Include IGNORE signals with score >= MIN_IGNORE_SCORE (false-negative candidates)
    MIN_IGNORE_SCORE = 50   # configurable; 50 = bottom of WATCH range
    MAX_SIGNALS_PER_RUN = 500  # hard cap to prevent multi-hour API runs

    def _load_signals(self) -> pd.DataFrame:
        since = datetime.now(timezone.utc) - timedelta(days=self._lookback_days)
        query = """
            SELECT TOP 500
                log_id, timestamp, asset, timeframe, direction,
                final_score, raw_score,
                score_order_flow, score_smc, score_vsa, score_context, score_bonus,
                regime, regime_multiplier,
                entry_price, stop_loss, take_profit_1, take_profit_2,
                classification, user_action
            FROM dbo.signal_log
            WHERE timestamp >= ?
              AND entry_price IS NOT NULL
              AND stop_loss IS NOT NULL
              AND take_profit_1 IS NOT NULL
              AND (
                  classification IN ('ALERT', 'WATCH')
                  OR final_score >= 50
              )
            ORDER BY timestamp ASC
        """
        try:
            cur = self._conn.cursor()
            cur.execute(query, since)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame([list(r) for r in rows], columns=cols)
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            logger.info("OutcomeLoader: loaded %d signals from DB", len(df))
            return df
        except Exception as exc:
            logger.error("OutcomeLoader: DB query failed: %s", exc)
            return pd.DataFrame()

    # ── Outcome cache ──────────────────────────────────────────────────────────

    def _load_outcomes_from_cache(self, signals: pd.DataFrame) -> dict:
        """Try to load from most-recent outcomes_*.json in temp dir."""
        files = sorted(self._temp_dir.glob("outcomes_*.json"), reverse=True)
        if not files:
            return {}
        latest = files[0]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            # data can be list of {log_id, outcome, ...} or dict keyed by log_id
            if isinstance(data, list):
                return {item["log_id"]: item for item in data if "log_id" in item}
            elif isinstance(data, dict):
                return data
        except Exception as exc:
            logger.warning("OutcomeLoader: failed to read cache %s: %s", latest, exc)
        return {}

    # ── Inline simulation ──────────────────────────────────────────────────────

    def _simulate_outcomes(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Label each signal WIN/LOSS/PENDING/NO_DATA by fetching Binance OHLCV."""
        now = datetime.now(timezone.utc)
        records = []

        for _, row in signals.iterrows():
            sig_ts = row["timestamp"]
            if pd.isnull(sig_ts):
                records.append({"log_id": row["log_id"], "outcome": "NO_DATA",
                                 "candles_to_hit": None, "mae_pct": None, "mfe_pct": None})
                continue

            age_h = (now - sig_ts).total_seconds() / 3600
            if age_h < MIN_SIGNAL_AGE_HOURS:
                records.append({"log_id": row["log_id"], "outcome": "PENDING",
                                 "candles_to_hit": None, "mae_pct": None, "mfe_pct": None})
                continue

            result = self._fetch_and_label(
                symbol      = row["asset"].replace("/", ""),
                start_ms    = int(sig_ts.timestamp() * 1000),
                direction   = row["direction"],
                entry       = float(row["entry_price"]),
                sl          = float(row["stop_loss"]),
                tp1         = float(row["take_profit_1"]),
                log_id      = row["log_id"],
            )
            records.append(result)
            time.sleep(0.2)   # Binance public rate limit

        out_df = pd.DataFrame(records).set_index("log_id")
        df = signals.copy()
        df = df.join(out_df, on="log_id")
        return df

    def _fetch_and_label(
        self, symbol: str, start_ms: int, direction: str,
        entry: float, sl: float, tp1: float, log_id: str,
    ) -> dict:
        base = {"log_id": log_id, "outcome": "NO_DATA",
                "candles_to_hit": None, "mae_pct": None, "mfe_pct": None}
        try:
            resp = requests.get(BINANCE_KLINES, params={
                "symbol": symbol, "interval": "5m",
                "startTime": start_ms, "limit": OUTCOME_WINDOW_CANDLES,
            }, timeout=10)
            resp.raise_for_status()
            candles = resp.json()
            if not candles:
                return base
        except Exception as exc:
            logger.debug("OHLCV fetch failed for %s: %s", symbol, exc)
            return base

        tp_hit = sl_hit = None
        max_adv = max_fav = 0.0

        for i, c in enumerate(candles):
            high, low = float(c[2]), float(c[3])
            if direction == "long":
                fav = (high - entry) / entry * 100
                adv = (entry - low)  / entry * 100
                tp_cond = high >= tp1
                sl_cond = low  <= sl
            else:
                fav = (entry - low)  / entry * 100
                adv = (high - entry) / entry * 100
                tp_cond = low  <= tp1
                sl_cond = high >= sl

            max_fav = max(max_fav, fav)
            max_adv = max(max_adv, adv)

            if tp_cond and tp_hit is None:
                tp_hit = i
            if sl_cond and sl_hit is None:
                sl_hit = i

        if tp_hit is not None and sl_hit is not None:
            outcome = "WIN" if tp_hit < sl_hit else "LOSS"
            candles_to_hit = min(tp_hit, sl_hit)
        elif tp_hit is not None:
            outcome = "WIN";  candles_to_hit = tp_hit
        elif sl_hit is not None:
            outcome = "LOSS"; candles_to_hit = sl_hit
        else:
            outcome = "PENDING"; candles_to_hit = None

        return {
            "log_id": log_id, "outcome": outcome,
            "candles_to_hit": candles_to_hit,
            "mae_pct": round(max_adv, 4),
            "mfe_pct": round(max_fav, 4),
        }

    # ── Helpers ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _add_rr_ratio(df: pd.DataFrame) -> pd.DataFrame:
        if "entry_price" in df.columns and "stop_loss" in df.columns and "take_profit_1" in df.columns:
            ep = df["entry_price"].astype(float)
            sl = df["stop_loss"].astype(float)
            tp = df["take_profit_1"].astype(float)
            sl_dist = (ep - sl).abs()
            tp_dist = (tp - ep).abs()
            df["rr_ratio"] = (tp_dist / sl_dist.replace(0, float("nan"))).round(2)
        else:
            df["rr_ratio"] = float("nan")
        return df

    @staticmethod
    def to_labeled(df: pd.DataFrame) -> pd.DataFrame:
        """Return only WIN/LOSS rows (exclude PENDING and NO_DATA)."""
        return df[df["outcome"].isin(["WIN", "LOSS"])].copy()
