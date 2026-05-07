"""
Config File Watcher
====================
Watches config.yaml for changes and triggers ConfigSystem.reload().
Uses the watchdog library for cross-platform file system events.

Satisfies: Requirement 15.11
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.config_system import ConfigSystem

logger = logging.getLogger(__name__)


class ConfigFileWatcher:
    """
    Background thread that watches config.yaml for modifications
    and calls ConfigSystem.reload() when the file changes.

    Usage:
        watcher = ConfigFileWatcher(config_system)
        watcher.start()
        # ... system runs ...
        watcher.stop()
    """

    def __init__(self, config_system: "ConfigSystem", poll_interval: float = 2.0) -> None:
        self._cfg = config_system
        self._interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_mtime: float = self._get_mtime()

    def start(self) -> None:
        """Start the background watcher thread."""
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="config-watcher",
            daemon=True,
        )
        self._thread.start()
        logger.info("Config watcher started (polling every %.1fs)", self._interval)

    def stop(self) -> None:
        """Stop the background watcher thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Config watcher stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_mtime(self) -> float:
        path = Path(self._cfg._path)
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(self._interval)
            current_mtime = self._get_mtime()
            if current_mtime != self._last_mtime:
                self._last_mtime = current_mtime
                logger.info("config.yaml changed — reloading...")
                try:
                    self._cfg.reload()
                except Exception as exc:  # noqa: BLE001
                    logger.error("Config reload failed: %s", exc)
