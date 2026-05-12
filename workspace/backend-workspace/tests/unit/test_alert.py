"""
Unit tests for Alert Builder, Time Invalidation, and Redis sender.

Satisfies: Requirements 18.1, 18.5, 17.4, 6.5
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from alert.builder import build_signal_card
from alert.invalidator import (
    compute_expiry, is_expired, check_time_invalidation, record_expiry,
)
from alert.sender import publish_alert
from strategies.signal import Signal, ScoreBreakdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_signal(
    classification: str = "ALERT",
    final_score: int = 80,
    candle_index: int = 100,
    expires_at_candle: int = 115,
    direction: str = "long",
) -> Signal:
    return Signal(
        strategy_name="test_strat",
        asset="BTC/USDT",
        timeframe="15m",
        direction=direction,
        candle_index=candle_index,
        candle_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit_1=52000.0,
        take_profit_2=54000.0,
        raw_score=100.0,
        final_score=final_score,
        score_breakdown=ScoreBreakdown(order_flow=25, smc=20, vsa=20, context=10, bonus=5),
        classification=classification,
        regime="TRENDING",
        regime_multiplier=1.0,
        funding_rate=0.0001,
        portfolio_heat=0.02,
        correlated_group_risk=0.01,
        expires_at_candle=expires_at_candle,
    )


# ---------------------------------------------------------------------------
# Alert Builder tests
# ---------------------------------------------------------------------------

class TestAlertBuilder:

    def test_all_required_fields_present(self):
        signal = make_signal()
        card = build_signal_card(signal)
        required = [
            "asset", "direction", "final_score", "entry_price",
            "stop_loss", "take_profit_1", "take_profit_2",
            "gross_rr", "net_rr", "score_breakdown",
            "regime", "expires_at_candle",
        ]
        for field in required:
            assert field in card, f"Missing field: {field}"

    def test_gross_rr_calculation(self):
        # entry=50000, sl=49000, tp1=52000
        # gross_rr = (52000-50000)/(50000-49000) = 2.0
        signal = make_signal()
        card = build_signal_card(signal)
        assert abs(card["gross_rr"] - 2.0) < 0.01

    def test_net_rr_less_than_gross_rr(self):
        signal = make_signal()
        card = build_signal_card(signal, fee_rate=0.001, slippage_pct=0.0002)
        assert card["net_rr"] < card["gross_rr"]

    def test_score_breakdown_has_all_sub_scores(self):
        signal = make_signal()
        card = build_signal_card(signal)
        sb = card["score_breakdown"]
        for sub in ["order_flow", "smc", "vsa", "context", "bonus"]:
            assert sub in sb

    def test_score_breakdown_values_correct(self):
        signal = make_signal()
        card = build_signal_card(signal)
        sb = card["score_breakdown"]
        assert sb["order_flow"] == 25
        assert sb["smc"] == 20
        assert sb["vsa"] == 20
        assert sb["context"] == 10
        assert sb["bonus"] == 5


# ---------------------------------------------------------------------------
# Time Invalidation tests
# ---------------------------------------------------------------------------

class TestTimeInvalidation:

    def test_compute_expiry(self):
        expiry = compute_expiry(candle_index=100, invalidation_candles=15)
        assert expiry == 115

    def test_is_expired_true_when_past_expiry(self):
        signal = make_signal(candle_index=100, expires_at_candle=115)
        assert is_expired(signal, current_candle_index=116) is True

    def test_is_expired_false_when_before_expiry(self):
        signal = make_signal(candle_index=100, expires_at_candle=115)
        assert is_expired(signal, current_candle_index=110) is False

    def test_is_expired_false_at_exact_expiry(self):
        signal = make_signal(candle_index=100, expires_at_candle=115)
        assert is_expired(signal, current_candle_index=115) is False

    def test_hard_expiry_after_15_candles(self):
        signal = make_signal(candle_index=100, expires_at_candle=115)
        result = check_time_invalidation(signal, current_candle_index=116)
        assert result.status == "EXPIRED"
        assert "Time limit" in result.reason

    def test_soft_expiry_when_bias_changed(self):
        signal = make_signal(candle_index=100, expires_at_candle=115)
        result = check_time_invalidation(
            signal, current_candle_index=106,
            htf_bias_changed=True,
        )
        assert result.status == "CANCELLED"
        assert "HTF bias" in result.reason

    def test_active_when_within_limits(self):
        signal = make_signal(candle_index=100, expires_at_candle=115)
        result = check_time_invalidation(signal, current_candle_index=103)
        assert result.status == "ACTIVE"

    def test_record_expiry_contains_price(self):
        signal = make_signal()
        record = record_expiry(signal, current_price=49500.0)
        assert record["user_action"] == "EXPIRED"
        assert record["expiry_price"] == 49500.0


# ---------------------------------------------------------------------------
# Redis sender tests
# ---------------------------------------------------------------------------

class TestRedisSender:

    @pytest.mark.asyncio
    async def test_alert_signal_is_published(self):
        mock_redis = AsyncMock()
        signal = make_signal(classification="ALERT", final_score=80)
        published = await publish_alert(mock_redis, signal)
        assert published is True
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "alerts:channel"

    @pytest.mark.asyncio
    async def test_watch_signal_not_published(self):
        mock_redis = AsyncMock()
        signal = make_signal(classification="WATCH", final_score=60)
        published = await publish_alert(mock_redis, signal)
        assert published is False
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignore_signal_not_published(self):
        mock_redis = AsyncMock()
        signal = make_signal(classification="IGNORE", final_score=30)
        published = await publish_alert(mock_redis, signal)
        assert published is False
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_published_payload_is_valid_json(self):
        import json
        mock_redis = AsyncMock()
        signal = make_signal(classification="ALERT", final_score=80)
        await publish_alert(mock_redis, signal)
        payload = mock_redis.publish.call_args[0][1]
        parsed = json.loads(payload)
        assert parsed["asset"] == "BTC/USDT"
        assert parsed["final_score"] == 80
