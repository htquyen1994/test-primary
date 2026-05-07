"""
Unit tests for FastAPI endpoints.

Satisfies: Requirements 18.1, 18.7, 18.10, 15.11
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app, _active_signals

client = TestClient(app)


class TestAPIEndpoints:

    def setup_method(self):
        _active_signals.clear()

    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_get_signals_empty(self):
        """GET /api/signals returns empty list when no active signals."""
        response = client.get("/api/signals")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_signals_returns_active(self):
        """GET /api/signals returns active ALERT signals."""
        _active_signals["sig_001"] = {
            "signal_id": "sig_001", "asset": "BTC/USDT",
            "direction": "long", "final_score": 80,
        }
        response = client.get("/api/signals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["signal_id"] == "sig_001"

    def test_confirm_signal_not_found(self):
        """Confirm non-existent signal returns 404."""
        response = client.post("/api/signals/nonexistent/confirm")
        assert response.status_code == 404

    def test_confirm_signal_success(self):
        """Confirm existing signal returns submitted status."""
        _active_signals["sig_002"] = {
            "signal_id": "sig_002", "asset": "ETH/USDT",
            "direction": "long", "final_score": 85,
        }
        response = client.post("/api/signals/sig_002/confirm")
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"

    def test_skip_signal_success(self):
        """Skip signal removes it from active queue."""
        _active_signals["sig_003"] = {
            "signal_id": "sig_003", "asset": "SOL/USDT",
            "direction": "short", "final_score": 76,
        }
        response = client.post(
            "/api/signals/sig_003/skip",
            json={"reason": "not confident"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"
        assert "sig_003" not in _active_signals

    def test_skip_signal_not_found(self):
        """Skip non-existent signal returns 404."""
        response = client.post("/api/signals/nonexistent/skip", json={})
        assert response.status_code == 404

    def test_get_portfolio(self):
        """GET /api/portfolio returns portfolio heat."""
        response = client.get("/api/portfolio")
        assert response.status_code == 200
        data = response.json()
        assert "portfolio_heat" in data
        assert "open_positions" in data

    def test_get_strategies(self):
        """GET /api/strategies returns registered strategy names."""
        response = client.get("/api/strategies")
        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data
        assert isinstance(data["strategies"], list)

    def test_get_backtest_results(self):
        """GET /api/backtest/results returns results dict."""
        response = client.get("/api/backtest/results")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "benchmark" in data

    def test_post_backtest_run(self):
        """POST /api/backtest/run queues a backtest."""
        response = client.post("/api/backtest/run", json={
            "strategy": "smc_ob_fvg",
            "asset": "BTC/USDT",
            "timeframe": "15m",
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
