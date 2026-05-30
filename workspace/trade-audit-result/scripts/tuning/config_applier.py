"""
Config Applier
===============
Applies a TuningRecommendation to the live DB (trading_params table).

Safety rules:
  - Requires explicit --apply flag (dry-run by default)
  - Creates a NEW trading_params row (version history preserved)
  - Old active row is de-activated AFTER new row is committed
  - Writes tuning metadata (win_rate, sample_size, date) into the new row
  - Never modifies Python source code
  - Never deletes existing rows

Apply flow:
  1. Read current active trading_params row
  2. Copy ALL columns to a new dict
  3. Patch columns from recommendations
  4. INSERT new row with version_tag = "auto_tuned_YYYY-MM-DD"
  5. Set new row is_active = 1, old row is_active = 0
  6. Commit atomically
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

from .recommender import TuningRecommendation, Recommendation

logger = logging.getLogger(__name__)

# Weight param names that map directly to trading_params columns
WEIGHT_PARAMS = {"weight_of", "weight_smc", "weight_vsa", "weight_ctx", "weight_bonus"}
THRESHOLD_PARAMS = {"score_alert_threshold", "score_watch_threshold"}


class ConfigApplier:
    """
    Applies recommendations to DB trading_params.
    Dry-run by default; pass dry_run=False to actually write.
    """

    def __init__(self, conn, dry_run: bool = True):
        self._conn = conn
        self._dry_run = dry_run

    def apply(self, rec: TuningRecommendation) -> dict:
        """
        Apply recommendations. Returns result dict with status and details.

        Args:
            rec: TuningRecommendation from Recommender.recommend()

        Returns:
            {
              "applied": bool,
              "dry_run": bool,
              "new_version_tag": str,
              "changes": list of {param, old, new},
              "skipped": list of {param, reason},
            }
        """
        result = {
            "applied": False,
            "dry_run": self._dry_run,
            "new_version_tag": "",
            "changes": [],
            "skipped": [],
        }

        if not rec.recommendations:
            logger.info("ConfigApplier: no recommendations to apply")
            result["skipped"].append({"reason": "no recommendations"})
            return result

        # Load current active params
        current = self._load_current()
        if not current:
            logger.error("ConfigApplier: no active trading_params found")
            result["skipped"].append({"reason": "no active trading_params row"})
            return result

        # Build patched params dict
        patched = dict(current)
        changes = []
        skipped = []

        for r in rec.recommendations:
            if r.param_group == "regime":
                # Regime blocking is not a simple column update — skip with note
                skipped.append({
                    "param": r.param_name,
                    "reason": "Regime blocking requires manual config change — see report",
                })
                continue

            col = r.param_name
            if col not in WEIGHT_PARAMS and col not in THRESHOLD_PARAMS:
                skipped.append({"param": col, "reason": f"Unknown column: {col}"})
                continue

            old_val = patched.get(col)
            new_val = r.new_value

            # Safety bounds for weights
            if col in WEIGHT_PARAMS:
                new_val = max(0.25, min(3.0, float(new_val)))

            # Safety bounds for thresholds
            if col == "score_alert_threshold":
                new_val = max(60, min(95, int(new_val)))
                # Ensure alert > watch
                watch_t = int(patched.get("score_watch_threshold", 55))
                if new_val <= watch_t:
                    skipped.append({
                        "param": col,
                        "reason": f"New alert threshold {new_val} <= watch threshold {watch_t}",
                    })
                    continue

            patched[col] = new_val
            changes.append({"param": col, "old": old_val, "new": new_val})

        if not changes:
            logger.info("ConfigApplier: no valid column changes after safety checks")
            result["skipped"] = skipped
            return result

        # Add tuning metadata
        patched["tuning_win_rate"]    = round(rec.win_rate, 4)
        patched["tuning_sample_size"] = rec.sample_n
        patched["tuning_date"]        = datetime.now(timezone.utc).isoformat()
        patched["tuning_auc_roc"]     = round(rec.optimized_auc, 4)

        version_tag = f"auto_tuned_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        version_note = (
            f"Auto-tuned: {len(changes)} param(s) changed. "
            f"N={rec.sample_n}, win_rate={rec.win_rate:.1%}, "
            f"AUC {rec.current_auc:.3f}→{rec.optimized_auc:.3f}"
        )

        result["new_version_tag"] = version_tag
        result["changes"] = changes
        result["skipped"] = skipped

        if self._dry_run:
            logger.info(
                "ConfigApplier DRY-RUN: would create version '%s' with %d change(s): %s",
                version_tag, len(changes),
                ", ".join(f"{c['param']}:{c['old']}→{c['new']}" for c in changes),
            )
            result["applied"] = False
            return result

        # Actual write
        try:
            self._write_new_version(
                current_id=current["id"],
                patched=patched,
                version_tag=version_tag,
                version_note=version_note,
            )
            result["applied"] = True
            logger.info(
                "ConfigApplier: applied '%s' — %d change(s): %s",
                version_tag, len(changes),
                ", ".join(f"{c['param']}:{c['old']}→{c['new']}" for c in changes),
            )
        except Exception as exc:
            logger.error("ConfigApplier: DB write failed: %s", exc)
            result["error"] = str(exc)

        return result

    # ── DB helpers ─────────────────────────────────────────────────────────────

    def _load_current(self) -> Optional[dict]:
        """Load the currently active trading_params row as a dict."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM dbo.trading_params WHERE is_active = 1 "
                "ORDER BY activated_at DESC"
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
        except Exception as exc:
            logger.error("ConfigApplier: failed to load current params: %s", exc)
            return None

    def _write_new_version(
        self,
        current_id: str,
        patched: dict,
        version_tag: str,
        version_note: str,
    ) -> None:
        """
        INSERT new row, set active, deactivate old row — in a transaction.
        """
        cur = self._conn.cursor()

        # Build INSERT statement from patched dict
        # Exclude identity/read-only columns
        skip_cols = {"id", "created_at", "activated_at"}
        insert_cols = [c for c in patched if c not in skip_cols]

        new_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Override version info
        patched_insert = dict(patched)
        patched_insert["version_tag"]  = version_tag
        patched_insert["version_note"] = version_note
        patched_insert["is_active"]    = 1

        col_list  = ", ".join(insert_cols)
        val_list  = ", ".join("?" for _ in insert_cols)
        vals      = [patched_insert.get(c) for c in insert_cols]

        cur.execute(
            f"INSERT INTO dbo.trading_params (id, created_at, activated_at, {col_list}) "
            f"VALUES (?, ?, ?, {val_list})",
            [new_id, now, now] + vals,
        )

        # Deactivate old row
        cur.execute(
            "UPDATE dbo.trading_params SET is_active = 0 WHERE id = ?",
            [current_id],
        )

        self._conn.commit()
        logger.info(
            "ConfigApplier: new row id=%s inserted, old id=%s deactivated",
            new_id, current_id,
        )
