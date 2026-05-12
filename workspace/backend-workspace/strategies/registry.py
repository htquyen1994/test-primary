"""
Strategy Registry — Plugin Architecture
=========================================
Decorator-based registry for strategy classes.
Enables adding new strategies without modifying existing code.

Usage:
    # Register a strategy
    @StrategyRegistry.register("my_strategy")
    class MyStrategy(BaseStrategy):
        ...

    # Load active strategies from config
    registry = StrategyRegistry()
    active = registry.load_active(config)

Satisfies: Requirements 16.1–16.7
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Type

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyNotFoundError(KeyError):
    """
    Raised when a strategy name in config.strategy.active is not registered.
    Satisfies: Requirement 16.4
    """
    def __init__(self, name: str, registered: List[str]) -> None:
        super().__init__(
            f"Strategy '{name}' not found in registry. "
            f"Registered strategies: {registered}. "
            f"Create a new file in strategies/ and decorate the class with "
            f"@StrategyRegistry.register('{name}')."
        )
        self.name = name
        self.registered = registered


class StrategyRegistry:
    """
    Runtime registry mapping strategy name strings to BaseStrategy subclasses.

    The registry is a module-level singleton dict populated by @register().
    StrategyRegistry instances provide methods to query and instantiate strategies.

    Satisfies: Requirements 16.1–16.7
    """

    # Module-level registry — shared across all instances
    _registry: Dict[str, Type[BaseStrategy]] = {}

    # ------------------------------------------------------------------
    # Registration (decorator)
    # ------------------------------------------------------------------

    @classmethod
    def register(cls, name: str):
        """
        Class decorator that registers a BaseStrategy subclass under `name`.

        Usage:
            @StrategyRegistry.register("smc_ob_fvg")
            class SMCOrderBlockFVGStrategy(BaseStrategy):
                ...

        Satisfies: Requirements 16.2, 16.5
        """
        def decorator(strategy_class: Type[BaseStrategy]) -> Type[BaseStrategy]:
            if not issubclass(strategy_class, BaseStrategy):
                raise TypeError(
                    f"@StrategyRegistry.register: {strategy_class.__name__} "
                    f"must be a subclass of BaseStrategy"
                )
            if name in cls._registry:
                logger.warning(
                    "Strategy '%s' already registered — overwriting with %s",
                    name, strategy_class.__name__,
                )
            cls._registry[name] = strategy_class
            logger.debug("Registered strategy: '%s' → %s", name, strategy_class.__name__)
            return strategy_class

        return decorator

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    @classmethod
    def list_registered(cls) -> List[str]:
        """
        Return all registered strategy names.
        Satisfies: Requirement 16.6
        """
        return sorted(cls._registry.keys())

    @classmethod
    def get_class(cls, name: str) -> Type[BaseStrategy]:
        """
        Return the strategy class for the given name.
        Raises StrategyNotFoundError if not registered.
        """
        if name not in cls._registry:
            raise StrategyNotFoundError(name, cls.list_registered())
        return cls._registry[name]

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    @classmethod
    def load_active(cls, config) -> Dict[str, BaseStrategy]:
        """
        Instantiate only the strategies listed in config.strategy.active.
        Passes the validated config object to each strategy constructor.

        Args:
            config: Validated AppConfig from ConfigSystem

        Returns:
            Dict mapping strategy name → instantiated BaseStrategy

        Raises:
            StrategyNotFoundError: if any name in active list is not registered
                                   (raised BEFORE any data is fetched — Req 16.4)

        Satisfies: Requirements 16.3, 16.4, 16.7
        """
        active_names: List[str] = config.strategy.active

        # Validate ALL names first — fail fast before instantiating anything
        for name in active_names:
            if name not in cls._registry:
                raise StrategyNotFoundError(name, cls.list_registered())

        instances: Dict[str, BaseStrategy] = {}
        for name in active_names:
            strategy_class = cls._registry[name]
            instances[name] = strategy_class(config)
            logger.info("Loaded strategy: '%s' (%s)", name, strategy_class.__name__)

        return instances

    @classmethod
    def auto_discover(cls, package: str = "strategies") -> None:
        """
        Auto-discover and import all strategy modules in the given package.
        This triggers the @register() decorators to populate the registry.

        Call this once at startup before load_active().

        Args:
            package: Python package name to scan (default "strategies")
        """
        try:
            pkg = importlib.import_module(package)
            pkg_path = getattr(pkg, "__path__", [])
            for _, module_name, _ in pkgutil.iter_modules(pkg_path):
                full_name = f"{package}.{module_name}"
                if full_name not in ("strategies.base", "strategies.registry",
                                     "strategies.signal"):
                    try:
                        importlib.import_module(full_name)
                        logger.debug("Auto-discovered: %s", full_name)
                    except ImportError as exc:
                        logger.warning("Could not import %s: %s", full_name, exc)
        except ImportError as exc:
            logger.warning("Auto-discovery failed for package '%s': %s", package, exc)
