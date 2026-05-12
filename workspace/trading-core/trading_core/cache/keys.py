"""
Redis Key Schema
=================
Centralized definition of all Redis keys used across services.
Prevents typos and makes key structure discoverable.

Usage:
    from trading_core.cache import RedisKeys

    key = RedisKeys.ohlcv("BTC/USDT", "15m")   # "ohlcv:BTC/USDT:15m"
    key = RedisKeys.ob_snap("ETH/USDT")          # "ob:ETH/USDT:snap"
    key = RedisKeys.delta("BTC/USDT")            # "delta:BTC/USDT:5m"
"""


class RedisKeys:
    """
    Static factory methods for all Redis keys.
    All keys follow the pattern: {domain}:{symbol}:{qualifier}
    """

    # ------------------------------------------------------------------
    # Market data (Layer 1 — Data Input)
    # ------------------------------------------------------------------

    @staticmethod
    def ohlcv(symbol: str, timeframe: str) -> str:
        """Ring buffer of OHLCV candles. e.g. ohlcv:BTC/USDT:15m"""
        return f"ohlcv:{symbol}:{timeframe}"

    @staticmethod
    def ob_snap(symbol: str) -> str:
        """Order book snapshot. e.g. ob:BTC/USDT:snap"""
        return f"ob:{symbol}:snap"

    @staticmethod
    def delta(symbol: str) -> str:
        """Cumulative buy-sell delta for current candle. e.g. delta:BTC/USDT:5m"""
        return f"delta:{symbol}:5m"

    @staticmethod
    def delta_history(symbol: str) -> str:
        """Rolling 24h delta history (96 values). e.g. delta_history:BTC/USDT"""
        return f"delta_history:{symbol}"

    @staticmethod
    def funding(symbol: str) -> str:
        """Funding rate. e.g. funding:BTC/USDT"""
        return f"funding:{symbol}"

    @staticmethod
    def poc(symbol: str) -> str:
        """Point of Control from Volume Profile. e.g. poc:BTC/USDT"""
        return f"poc:{symbol}"

    # ------------------------------------------------------------------
    # Engine state (Layer 2 — AI Engine)
    # ------------------------------------------------------------------

    @staticmethod
    def regime(symbol: str) -> str:
        """Current market regime. e.g. regime:BTC/USDT"""
        return f"regime:{symbol}"

    @staticmethod
    def daily_bias(symbol: str) -> str:
        """Daily macro bias: BULL/BEAR/NEUTRAL. e.g. daily_bias:BTC/USDT"""
        return f"daily_bias:{symbol}"

    @staticmethod
    def correlation_matrix() -> str:
        """Rolling Pearson correlation matrix."""
        return "correlation:matrix"

    # ------------------------------------------------------------------
    # Phase 9 — Risk protection
    # ------------------------------------------------------------------

    @staticmethod
    def btc_guard_spike() -> str:
        """BTC spike state + cooldown. e.g. btc_guard:spike"""
        return "btc_guard:spike"

    @staticmethod
    def circuit_breaker_locked() -> str:
        """Circuit breaker fast-path cache: '1' or '0'."""
        return "circuit_breaker:locked"

    @staticmethod
    def circuit_breaker_recent_losses() -> str:
        """Recent loss timestamps for consecutive loss check."""
        return "circuit_breaker:recent_losses"

    @staticmethod
    def open_positions() -> str:
        """Hash of open positions: {asset: risk_pct}. Used by portfolio heat."""
        return "portfolio:open_positions"

    # ------------------------------------------------------------------
    # Pub/sub channels
    # ------------------------------------------------------------------

    class Channels:
        """Redis pub/sub channel names."""
        CANDLE_CLOSE      = "candle_close"
        ALERTS            = "alerts:channel"
        LOGS              = "logs:channel"
        CANCEL_ALL_ALERTS = "cancel_all_alerts"
        BTC_SPIKE         = "btc_spike"
        CIRCUIT_BREAKER   = "circuit_breaker:events"
        MOCK_FILLS        = "mock_exchange:fills"
        MOCK_PNL          = "mock_exchange:pnl"
