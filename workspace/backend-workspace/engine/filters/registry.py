"""
Filter Registry — Plugin Architecture
=======================================
Decorator-based registry for signal filters.
Mirrors StrategyRegistry pattern for consistency.

Usage:
    # Register a filter (in its own file):
    @FilterRegistry.register("my_filter")
    class MyFilter(BaseSignalFilter):
        name = "my_filter"
        def apply(self, context): ...

    # Load active filters from config list:
    filters = FilterRegistry.load_active(["mtf_bias", "btc_guard"])

    # Apply in pipeline:
    for f in filters:
        result = f.apply(context)
        if not result.passed:
            return
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Type

from engine.filters.base import BaseSignalFilter

logger = logging.getLogger(__name__)


class FilterNotFoundError(KeyError):
    """Raised when a filter name in active list is not registered."""
    def __init__(self, name: str, registered: List[str]) -> None:
        super().__init__(
            f"Filter '{name}' not found in registry. "
            f"Registered filters: {registered}. "
            f"Create a file in engine/filters/ and decorate with "
            f"@FilterRegistry.register('{name}')."
        )
        self.name = name
        self.registered = registered


class FilterRegistry:
    """
    Runtime registry mapping filter name strings to BaseSignalFilter subclasses.

    Module-level singleton dict populated by @register() decorator.
    """

    _registry: Dict[str, Type[BaseSignalFilter]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @classmethod
    def register(cls, name: str):
        """
        Class decorator that registers a BaseSignalFilter subclass.

        Usage:
            @FilterRegistry.register("mtf_bias")
            class MTFBiasFilter(BaseSignalFilter):
                name = "mtf_bias"
                ...
        """
        def decorator(filter_class: Type[BaseSignalFilter]) -> Type[BaseSignalFilter]:
            if not issubclass(filter_class, BaseSignalFilter):
                raise TypeError(
                    f"@FilterRegistry.register: {filter_class.__name__} "
                    f"must be a subclass of BaseSignalFilter"
                )
            if name in cls._registry:
                logger.warning(
                    "Filter '%s' already registered — overwriting with %s",
                    name, filter_class.__name__,
                )
            cls._registry[name] = filter_class
            logger.debug("Registered filter: '%s' → %s", name, filter_class.__name__)
            return filter_class
        return decorator

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @classmethod
    def list_registered(cls) -> List[str]:
        """Return all registered filter names."""
        return sorted(cls._registry.keys())

    @classmethod
    def get_class(cls, name: str) -> Type[BaseSignalFilter]:
        """Return the filter class for the given name."""
        if name not in cls._registry:
            raise FilterNotFoundError(name, cls.list_registered())
        return cls._registry[name]

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    @classmethod
    def load_active(cls, enabled: List[str]) -> List[BaseSignalFilter]:
        """
        Instantiate only the filters in the enabled list.
        Preserves order — filters run in the order listed.

        Args:
            enabled: List of filter name strings from config

        Returns:
            List of instantiated BaseSignalFilter objects

        Raises:
            FilterNotFoundError: if any name is not registered
        """
        # Auto-discover first to ensure all filters are registered
        cls.auto_discover()

        # Validate all names before instantiating any
        for name in enabled:
            if name not in cls._registry:
                raise FilterNotFoundError(name, cls.list_registered())

        instances = []
        for name in enabled:
            instance = cls._registry[name]()
            instances.append(instance)
            logger.debug("Loaded filter: '%s'", name)

        logger.info(
            "Active filters (%d): %s",
            len(instances), [f.name for f in instances],
        )
        return instances

    @classmethod
    def auto_discover(cls, package: str = "engine.filters") -> None:
        """
        Auto-import all filter modules to trigger @register() decorators.
        Called automatically by load_active().
        """
        try:
            pkg = importlib.import_module(package)
            pkg_path = getattr(pkg, "__path__", [])
            skip = {
                "engine.filters.base",
                "engine.filters.registry",
                "engine.filters.__init__",
            }
            for _, module_name, _ in pkgutil.iter_modules(pkg_path):
                full_name = f"{package}.{module_name}"
                if full_name not in skip:
                    try:
                        importlib.import_module(full_name)
                        logger.debug("Auto-discovered filter module: %s", full_name)
                    except ImportError as exc:
                        logger.warning("Could not import filter %s: %s", full_name, exc)
        except ImportError as exc:
            logger.warning("Filter auto-discovery failed for '%s': %s", package, exc)
