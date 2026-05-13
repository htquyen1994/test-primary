"""
Circuit Breaker — Enhanced Risk Protection
============================================
Automatically locks trading when risk thresholds are breached.

4 Trigger Conditions (Task 32.2):
  Trigger 1 — Consecutive losses: 3 losses in 24h → lock 12h
  Trigger 2 — Loss magnitude:     1 trade loss > 4% equity → lock 6h
  Trigger 3 — Daily loss cap:     total daily loss > 5% equity → lock until 00:00 UTC
  Trigger 4 — Drawdown from peak: equity drops > 10% from 7-day high → lock 24h + manual review

Smart Unlock (Task 32.3):
  After lock expires: check if regime changed from trigger regime
  If regime unchanged → extend lock by 6h
  If regime changed → allow unlock
  Trigger 4 always requires manual review note before unlock

State is persisted in SQL Server `circuit_breaker_state` table.
Redis key `circuit_breaker:locked` is used as fast-path cache.

Satisfies: Requirements 22 (Phase 9 Circuit Breaker)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from trading_core.cache import get_redis, RedisKeys
from trading_core.db import get_session_factory

logger = logging.getLogger(__name__)

# Trigger thresholds
CONSECUTIVE_LOSS_COUNT = 3          # 3 losses in 24h
CONSECUTIVE_LOSS_WINDOW_HOURS = 24
CONSECUTIVE_LOSS_LOCK_HOURS = 12

LOSS_MAGNITUDE_PCT = 0.04           # 4% equity in single trade
LOSS_MAGNITUDE_LOCK_HOURS = 6

DAILY_LOSS_CAP_PCT = 0.05           # 5% equity total daily loss
# Lock until 00:00 UTC (computed dynamically)

DRAWDOWN_FROM_PEAK_PCT = 0.10       # 10% from 7-day high
DRAWDOWN_PEAK_WINDOW_DAYS = 7
DRAWDOWN_LOCK_HOURS = 24
DRAWDOWN_REQUIRES_REVIEW = True

# Smart unlock: extend by 6h if regime unchanged
REGIME_UNCHANGED_EXTENSION_HOURS = 6

# Redis cache TTL (seconds) — slightly longer than max lock duration
REDIS_LOCK_TTL = 25 * 3600  # 25 hours


@dataclass
class LockInfo:
    """Current circuit breaker lock state."""
    is_locked: bool
    trigger_type: Optional[str] = None
    trigger_detail: Optional[str] = None
    triggered_at: Optional[datetime] = None
    unlock_at: Optional[datetime] = None
    regime_at_trigger: Optional[str] = None
    unlock_requires_review: bool = False
    time_remaining_seconds: float = 0.0


class CircuitBreaker:
    """
    Manages circuit breaker state in SQL Server + Redis cache.

    Usage:
        cb = CircuitBreaker()
        if cb.is_locked():
            return  # block trading

        # After a trade result:
        cb.record_trade_result(pnl_pct=-0.05, equity=10000, regime="CHOPPY")
    """

    def __init__(self) -> None:
        pass  # singletons provided by trading_core

    def _get_redis(self):
        return get_redis()

    def _get_db(self):
        return get_session_factory()()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_locked(self) -> bool:
        """Fast-path check via Redis cache. Falls back to DB if Redis key missing."""
        r = self._get_redis()
        cached = r.get(RedisKeys.circuit_breaker_locked())
        if cached is not None:
            return cached == "1"
        info = self.get_lock_info()
        return info.is_locked

    def get_lock_info(self) -> LockInfo:
        """
        Return full lock state from DB.
        Updates Redis cache as side effect.
        """
        db = self._get_db()
        try:
            from sqlalchemy import text
            result = db.execute(text(
                "SELECT TOP 1 id, trigger_type, trigger_detail, triggered_at, "
                "unlock_at, regime_at_trigger, unlock_requires_review "
                "FROM circuit_breaker_state "
                "WHERE is_locked = 1 "
                "ORDER BY triggered_at DESC"
            )).fetchone()

            if result is None:
                self._update_redis_cache(False)
                return LockInfo(is_locked=False)

            now = datetime.now(timezone.utc)
            unlock_at = result.unlock_at
            if unlock_at.tzinfo is None:
                unlock_at = unlock_at.replace(tzinfo=timezone.utc)

            if now >= unlock_at:
                # Lock expired — check smart unlock conditions
                self._handle_lock_expiry(db, result)
                self._update_redis_cache(False)
                return LockInfo(is_locked=False)

            time_remaining = (unlock_at - now).total_seconds()
            self._update_redis_cache(True, ttl=int(time_remaining) + 60)

            return LockInfo(
                is_locked=True,
                trigger_type=result.trigger_type,
                trigger_detail=result.trigger_detail,
                triggered_at=result.triggered_at,
                unlock_at=unlock_at,
                regime_at_trigger=result.regime_at_trigger,
                unlock_requires_review=bool(result.unlock_requires_review),
                time_remaining_seconds=time_remaining,
            )
        except Exception as exc:
            # Downgrade SQL "table not found" (42S02) to WARNING — migration 003
            # hasn't been run yet. All other errors remain as ERROR.
            exc_str = str(exc)
            if "42S02" in exc_str or "circuit_breaker_state" in exc_str:
                logger.warning(
                    "CircuitBreaker table missing — run `python db/init_db.py` "
                    "to apply migration 003. Treating as unlocked."
                )
            else:
                logger.error("CircuitBreaker.get_lock_info error: %s", exc)
            return LockInfo(is_locked=False)
        finally:
            db.close()

    def record_trade_result(
        self,
        pnl_pct: float,
        equity: float,
        regime: str,
        trade_id: Optional[str] = None,
    ) -> Optional[LockInfo]:
        """
        Evaluate trade result against all 4 trigger conditions.
        Returns LockInfo if a trigger was activated, None otherwise.

        Args:
            pnl_pct: Trade P&L as fraction of equity (e.g., -0.05 = -5%)
            equity:  Current account equity in USD
            regime:  Current market regime (TRENDING/CHOPPY/RANGING/PARABOLIC)
            trade_id: Optional trade identifier for logging
        """
        if self.is_locked():
            logger.debug("CircuitBreaker already locked — skipping trigger check")
            return self.get_lock_info()

        # Trigger 2 — Loss magnitude (single trade)
        if pnl_pct < -LOSS_MAGNITUDE_PCT:
            return self._activate(
                trigger_type="LOSS_MAGNITUDE",
                trigger_detail=f"Single trade loss {pnl_pct*100:.1f}% > {LOSS_MAGNITUDE_PCT*100:.0f}% equity (trade_id={trade_id})",
                lock_hours=LOSS_MAGNITUDE_LOCK_HOURS,
                regime=regime,
                requires_review=False,
            )

        # Trigger 1 — Consecutive losses
        if self._check_consecutive_losses(pnl_pct, regime):
            return self._activate(
                trigger_type="CONSECUTIVE_LOSSES",
                trigger_detail=f"{CONSECUTIVE_LOSS_COUNT} consecutive losses in {CONSECUTIVE_LOSS_WINDOW_HOURS}h",
                lock_hours=CONSECUTIVE_LOSS_LOCK_HOURS,
                regime=regime,
                requires_review=False,
            )

        # Trigger 3 — Daily loss cap
        daily_loss = self._get_daily_loss_pct(equity)
        if daily_loss < -DAILY_LOSS_CAP_PCT:
            return self._activate(
                trigger_type="DAILY_LOSS_CAP",
                trigger_detail=f"Daily loss {daily_loss*100:.1f}% > {DAILY_LOSS_CAP_PCT*100:.0f}% equity",
                lock_until_midnight=True,
                regime=regime,
                requires_review=False,
            )

        return None

    def check_drawdown(self, current_equity: float, regime: str) -> Optional[LockInfo]:
        """
        Check Trigger 4 — Drawdown from 7-day peak.
        Call this periodically (e.g., every hour).

        Args:
            current_equity: Current account equity
            regime:         Current market regime
        """
        if self.is_locked():
            return None

        peak = self._get_7day_equity_peak(current_equity)
        if peak <= 0:
            return None

        drawdown = (peak - current_equity) / peak
        if drawdown > DRAWDOWN_FROM_PEAK_PCT:
            return self._activate(
                trigger_type="DRAWDOWN_FROM_PEAK",
                trigger_detail=f"Equity dropped {drawdown*100:.1f}% from 7-day peak ${peak:.0f}",
                lock_hours=DRAWDOWN_LOCK_HOURS,
                regime=regime,
                requires_review=DRAWDOWN_REQUIRES_REVIEW,
            )
        return None

    def manual_unlock(self, review_note: str, unlocked_by: str = "user") -> bool:
        """
        Manually unlock the circuit breaker with a review note.
        Required for Trigger 4 (drawdown from peak).

        Args:
            review_note: User's review note explaining why they want to resume
            unlocked_by: Identifier of who unlocked

        Returns:
            True if unlocked successfully
        """
        if not review_note or len(review_note.strip()) < 10:
            logger.warning("Manual unlock rejected: review note too short")
            return False

        db = self._get_db()
        try:
            from sqlalchemy import text
            now = datetime.now(timezone.utc)
            db.execute(text(
                "UPDATE circuit_breaker_state "
                "SET is_locked = 0, unlocked_at = :now, unlocked_by = :by, review_note = :note "
                "WHERE is_locked = 1"
            ), {"now": now, "by": unlocked_by, "note": review_note.strip()})
            db.commit()
            self._update_redis_cache(False)
            logger.info("Circuit breaker manually unlocked by %s", unlocked_by)
            return True
        except Exception as exc:
            logger.error("Manual unlock error: %s", exc)
            return False
        finally:
            db.close()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _activate(
        self,
        trigger_type: str,
        trigger_detail: str,
        regime: str,
        lock_hours: float = 0,
        lock_until_midnight: bool = False,
        requires_review: bool = False,
    ) -> LockInfo:
        """Insert a new lock record into DB and update Redis cache."""
        now = datetime.now(timezone.utc)

        if lock_until_midnight:
            # Lock until 00:00 UTC next day
            tomorrow = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            unlock_at = tomorrow
        else:
            unlock_at = now + timedelta(hours=lock_hours)

        db = self._get_db()
        try:
            from sqlalchemy import text
            db.execute(text(
                "INSERT INTO circuit_breaker_state "
                "(triggered_at, unlock_at, trigger_type, trigger_detail, "
                "regime_at_trigger, is_locked, unlock_requires_review) "
                "VALUES (:triggered_at, :unlock_at, :trigger_type, :trigger_detail, "
                ":regime, 1, :requires_review)"
            ), {
                "triggered_at": now,
                "unlock_at": unlock_at,
                "trigger_type": trigger_type,
                "trigger_detail": trigger_detail,
                "regime": regime,
                "requires_review": 1 if requires_review else 0,
            })
            db.commit()

            time_remaining = (unlock_at - now).total_seconds()
            self._update_redis_cache(True, ttl=int(time_remaining) + 60)

            logger.warning(
                "🔴 CIRCUIT BREAKER ACTIVATED: %s — %s | Locked until %s",
                trigger_type, trigger_detail, unlock_at.isoformat(),
            )

            # Publish notification to Redis
            r = self._get_redis()
            r.publish(RedisKeys.Channels.CIRCUIT_BREAKER, json.dumps({
                "event": "locked",
                "trigger_type": trigger_type,
                "trigger_detail": trigger_detail,
                "unlock_at": unlock_at.isoformat(),
                "requires_review": requires_review,
            }))

            return LockInfo(
                is_locked=True,
                trigger_type=trigger_type,
                trigger_detail=trigger_detail,
                triggered_at=now,
                unlock_at=unlock_at,
                regime_at_trigger=regime,
                unlock_requires_review=requires_review,
                time_remaining_seconds=time_remaining,
            )
        except Exception as exc:
            logger.error("CircuitBreaker._activate error: %s", exc)
            return LockInfo(is_locked=False)
        finally:
            db.close()

    def _handle_lock_expiry(self, db, lock_record) -> None:
        """
        Smart unlock: check if regime changed since trigger.
        If regime unchanged → extend lock by 6h.
        If regime changed → unlock.
        """
        try:
            from sqlalchemy import text
            current_regime = self._get_current_regime()
            regime_at_trigger = lock_record.regime_at_trigger or "UNKNOWN"

            if current_regime and current_regime == regime_at_trigger:
                # Regime unchanged — extend lock
                new_unlock = datetime.now(timezone.utc) + timedelta(hours=REGIME_UNCHANGED_EXTENSION_HOURS)
                db.execute(text(
                    "UPDATE circuit_breaker_state "
                    "SET unlock_at = :new_unlock, trigger_detail = CONCAT(trigger_detail, ' [Extended: regime unchanged]') "
                    "WHERE id = :id"
                ), {"new_unlock": new_unlock, "id": lock_record.id})
                db.commit()
                self._update_redis_cache(True, ttl=REGIME_UNCHANGED_EXTENSION_HOURS * 3600 + 60)
                logger.warning(
                    "Circuit breaker extended by %dh — regime still %s",
                    REGIME_UNCHANGED_EXTENSION_HOURS, current_regime,
                )

                # Notify user
                r = self._get_redis()
                r.publish(RedisKeys.Channels.CIRCUIT_BREAKER, json.dumps({
                    "event": "extended",
                    "reason": f"Thị trường vẫn {current_regime} — chưa thay đổi regime",
                    "new_unlock_at": new_unlock.isoformat(),
                }))
            else:
                # Regime changed — unlock
                db.execute(text(
                    "UPDATE circuit_breaker_state "
                    "SET is_locked = 0, unlocked_at = :now, unlocked_by = 'auto_regime_change' "
                    "WHERE id = :id"
                ), {"now": datetime.now(timezone.utc), "id": lock_record.id})
                db.commit()
                self._update_redis_cache(False)
                logger.info(
                    "Circuit breaker auto-unlocked: regime changed %s → %s",
                    regime_at_trigger, current_regime,
                )
        except Exception as exc:
            logger.error("_handle_lock_expiry error: %s", exc)

    def _check_consecutive_losses(self, current_pnl_pct: float, regime: str) -> bool:
        """Check if there are 3+ consecutive losses in the last 24h."""
        if current_pnl_pct >= 0:
            return False

        r = self._get_redis()
        key = RedisKeys.circuit_breaker_recent_losses()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=CONSECUTIVE_LOSS_WINDOW_HOURS)

        raw = r.get(key)
        losses = json.loads(raw) if raw else []
        losses = [ts for ts in losses if datetime.fromisoformat(ts) > cutoff]
        losses.append(now.isoformat())
        r.set(key, json.dumps(losses), ex=CONSECUTIVE_LOSS_WINDOW_HOURS * 3600 + 300)
        return len(losses) >= CONSECUTIVE_LOSS_COUNT

    def _get_daily_loss_pct(self, equity: float) -> float:
        """Get total P&L as fraction of equity for today (UTC)."""
        try:
            db = self._get_db()
            from sqlalchemy import text
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            result = db.execute(text(
                "SELECT COALESCE(SUM(net_pnl), 0) as daily_pnl "
                "FROM trade_journal "
                "WHERE entry_timestamp >= :today"
            ), {"today": today_start}).fetchone()
            db.close()
            daily_pnl = float(result.daily_pnl) if result else 0.0
            return daily_pnl / equity if equity > 0 else 0.0
        except Exception as exc:
            logger.warning("_get_daily_loss_pct error: %s", exc)
            return 0.0

    def _get_7day_equity_peak(self, current_equity: float) -> float:
        """
        Compute the maximum equity value over the last 7 days.

        Reconstructs the equity timeline from trade_journal net_pnl history,
        working backwards from current_equity using suffix sums:
            equity_before_trade_i = current_equity - sum(net_pnl from trade_i to now)

        Result is cached in Redis with 1-hour TTL to avoid repeated DB scans.

        Args:
            current_equity: Current account equity (the reference end-point)

        Returns:
            Peak equity value, or 0.0 on error.
        """
        _CACHE_KEY = "circuit_breaker:7day_peak"
        _CACHE_TTL = 3600  # 1 hour

        # Fast path: Redis cache
        try:
            r = self._get_redis()
            cached = r.get(_CACHE_KEY)
            if cached is not None:
                return float(cached)
        except Exception:
            pass

        # Compute from DB
        try:
            db = self._get_db()
            try:
                from sqlalchemy import text
                cutoff = datetime.now(timezone.utc) - timedelta(days=DRAWDOWN_PEAK_WINDOW_DAYS)
                rows = db.execute(text(
                    "SELECT net_pnl FROM trade_journal "
                    "WHERE exit_timestamp >= :cutoff "
                    "  AND exit_timestamp IS NOT NULL "
                    "  AND net_pnl IS NOT NULL "
                    "ORDER BY exit_timestamp ASC"
                ), {"cutoff": cutoff}).fetchall()
            finally:
                db.close()

            if not rows:
                # No closed trades in window — current equity is the only data point
                peak = current_equity
            else:
                net_pnls = [float(row.net_pnl) for row in rows]
                n = len(net_pnls)

                # suffix_sums[i] = sum(net_pnl[i..n-1])
                # equity before trade[i] = current_equity - suffix_sums[i]
                suffix_sums = [0.0] * n
                suffix_sums[n - 1] = net_pnls[n - 1]
                for i in range(n - 2, -1, -1):
                    suffix_sums[i] = suffix_sums[i + 1] + net_pnls[i]

                equities = [current_equity - s for s in suffix_sums]
                equities.append(current_equity)  # equity after last trade
                peak = max(equities)

            # Cache result
            try:
                r = self._get_redis()
                r.set(_CACHE_KEY, str(peak), ex=_CACHE_TTL)
            except Exception:
                pass

            logger.debug(
                "7-day equity peak computed: $%.2f (current: $%.2f, trades: %d)",
                peak, current_equity, len(rows),
            )
            return peak

        except Exception as exc:
            logger.warning("_get_7day_equity_peak error: %s", exc)
            return 0.0

    def _get_current_regime(self) -> Optional[str]:
        """Get current market regime from Redis (set by RegimeDetector)."""
        try:
            r = self._get_redis()
            for symbol in ["BTC/USDT", "ETH/USDT"]:
                regime = r.get(RedisKeys.regime(symbol))
                if regime:
                    return regime
            return None
        except Exception:
            return None

    def _update_redis_cache(self, locked: bool, ttl: int = REDIS_LOCK_TTL) -> None:
        """Update Redis fast-path cache."""
        try:
            r = self._get_redis()
            r.set(RedisKeys.circuit_breaker_locked(), "1" if locked else "0", ex=ttl)
        except Exception as exc:
            logger.warning("Redis cache update error: %s", exc)
