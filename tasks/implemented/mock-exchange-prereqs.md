# Task List — Pre-conditions cho Mock Exchange + Audit Feature

> **Dựa trên:** `tasks/designs/mock-exchange-audit.md` — Phase A
> **Phạm vi:** Chỉ `backend-workspace` — minimal changes, không touch scoring logic
> **Thứ tự:** Sequential TASK-26 → TASK-30 (phụ thuộc lẫn nhau theo thứ tự)
> **Bắt buộc hoàn thành trước khi implement `mock-exchange-workspace`**

---

## TASK-26 — Refactor `TradeExecutor._submit_with_retry()` dùng `ExchangeInterface`

- **Status:** TODO
- **Files:** `workspace/backend-workspace/trade/executor.py:152–215`
- **Vấn đề:** `_submit_with_retry()` gọi ccxt raw methods (`create_limit_order`, `create_market_order`, `create_order` với ccxt params) không tồn tại trên `ExchangeInterface`. Inject `MockExchange` sẽ crash ngay lập tức.
- **Fix:**
  - Import `OrderSide`, `OrderType` từ `trading_core.exchange.interface`
  - Rewrite 3 order type branches thành `ExchangeInterface.create_order()`:
    ```python
    # limit entry
    order = await self._exchange.create_order(
        symbol=asset,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        order_type=OrderType.LIMIT,
        amount=amount,
        price=price,
        client_order_id=client_order_id,
    )
    # stop_loss
    order = await self._exchange.create_order(
        symbol=asset, side=sl_side,
        order_type=OrderType.STOP_LOSS, amount=amount, price=price,
    )
    # take_profit
    order = await self._exchange.create_order(
        symbol=asset, side=tp_side,
        order_type=OrderType.TAKE_PROFIT, amount=amount, price=price,
    )
    ```
  - Update return value: `Order.order_id` thay vì `order.get("id")`
  - Update `ExecutionResult.actual_fill_price`: lấy từ `Order.fill_price` thay vì `order.get("price")`
  - Giữ nguyên `_assert_testnet_safe()` — vẫn guard cho live trading
- **Lưu ý:** Sau khi refactor xong, `self._exchange` trong `TradeExecutor` cần được inject với `MockExchangeHttpClient` (xem TASK-31) khi chạy mock mode. TASK-26 chỉ đảm bảo interface contract đúng — chưa tạo concrete implementation.
- **Phụ thuộc:** TASK-31 phải complete trước khi mock mode có thể chạy end-to-end.
- **Test:** Unit test verify `TradeExecutor` có thể inject bất kỳ `ExchangeInterface` mock nào mà không cần ccxt object.

---

## TASK-27 — Refactor `_persist_signal()` return `signal_id`

- **Status:** TODO
- **Files:** `workspace/backend-workspace/engine/scoring_service.py:528–560`, `workspace/backend-workspace/api/signal_log_writer.py`
- **Vấn đề:** `_persist_signal()` không return gì — `signal_id` bị mất sau khi INSERT. Audit log không thể link về `signal_log` trong backend DB.
- **Fix:**
  - `write_signal_log()` trong `signal_log_writer.py` phải return inserted row ID:
    ```python
    def write_signal_log(signal: Signal, db) -> int:
        db_obj = SignalLog(...)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj.id  # ← thêm dòng này
    ```
  - `_persist_signal()` return `Optional[str]`:
    ```python
    def _persist_signal(self, ...) -> Optional[str]:
        try:
            ...
            signal_log_id = write_signal_log(signal_obj, db)
            db.close()
            return str(signal_log_id)
        except Exception as exc:
            logger.warning("Failed to persist signal_log: %s", exc)
            return None
    ```
  - Trong `_run_cycle()`, capture return value:
    ```python
    signal_id = self._persist_signal(...)
    ```
- **Test:** Unit test verify `_persist_signal()` return đúng ID sau INSERT. Verify `None` khi DB unavailable.

---

## TASK-28 — Audit hook tại mọi exit point của `_run_cycle()`

- **Status:** TODO
- **Files:** `workspace/backend-workspace/engine/scoring_service.py`
- **Vấn đề:** Filter block early return tại line 279 thoát trước bất kỳ audit logic nào ở cuối function. Mọi signal bị CB locked, BTC Guard, MTF block đều bị miss hoàn toàn — đây là phần data quan trọng nhất cho counterfactual analysis.
- **Phụ thuộc:** TASK-27 (cần `signal_id` từ `_persist_signal()`)
- **Fix:**
  - Khởi tạo `_audit` dict ngay đầu `_run_cycle()` với default values
  - Thêm helper `_emit_audit(audit_data)` — push vào Redis list, non-blocking
  - Thêm helper `_map_filter_to_reason(filter_name)` — map tên filter sang enum string
  - Gọi `_emit_audit(_audit)` tại mỗi exit point:

  ```python
  async def _run_cycle(self, symbol: str, timeframe: str) -> None:
      _audit = {
          "type": "signal_snapshot",
          "symbol": symbol,
          "timeframe": timeframe,
          "timestamp_candle_close": datetime.now(timezone.utc).isoformat(),
          "signal_result": "NO_SIGNAL",
          "final_score": 0,
          "score_breakdown": None,
          "regime": None,
          "regime_multiplier": None,
          "btc_guard_active": False,
          "circuit_breaker_locked": False,
          "blocking_reason": None,
          "blocking_detail": None,
          "entry_price_proposed": None,
          "sl_proposed": None,
          "tp1_proposed": None,
          "atr_value": None,
          "adx_value": None,
          "delta_value": None,
          "delta_threshold": None,
          "funding_rate": None,
          "ob_available": False,
          "signal_id": None,
      }

      # ... existing early exit nếu không đủ candles ...
      # (không cần audit — chưa có data)

      # ... load inputs, compute indicators ...
      _audit["atr_value"] = atr_val
      _audit["adx_value"] = adx_val
      _audit["delta_value"] = delta
      _audit["delta_threshold"] = dynamic_threshold
      _audit["funding_rate"] = funding_rate
      _audit["ob_available"] = order_book_available
      _audit["regime"] = regime_state.regime
      _audit["regime_multiplier"] = regime_state.score_multiplier

      for f in active_filters:
          result = f.apply(filter_context)
          if not result.passed:
              _audit["blocking_reason"] = self._map_filter_to_reason(f.name)
              _audit["blocking_detail"] = result.block_reason
              _audit["btc_guard_active"] = f.name == "btc_guard"
              _audit["circuit_breaker_locked"] = f.name == "circuit_breaker"
              self._emit_audit(_audit)  # ← emit trước early return
              publish_log(r, log_entry)
              return
          ...

      # ... scoring ...
      _audit["final_score"] = score.final_score
      _audit["score_breakdown"] = {
          "of": of.score, "smc": smc.score,
          "vsa": vsa.score, "ctx": ctx.score, "bonus": bonus,
      }
      _audit["signal_result"] = "SIGNAL" if score.classification == "ALERT" else "NO_SIGNAL"

      signal_id = self._persist_signal(...)
      _audit["signal_id"] = signal_id
      _audit["entry_price_proposed"] = float(ohlcv.iloc[-1]["close"])
      _audit["sl_proposed"] = stop_loss
      _audit["tp1_proposed"] = tp1

      self._emit_audit(_audit)  # ← emit tại exit bình thường

  def _emit_audit(self, audit_data: dict) -> None:
      if not getattr(self, "_audit_enabled", False):
          return
      try:
          r = self._get_redis()
          r.rpush("audit:pending_snapshots", json.dumps(audit_data))
      except Exception as exc:
          logger.warning("Audit emit failed (non-blocking): %s", exc)

  def _map_filter_to_reason(self, filter_name: str) -> str:
      return {
          "mtf_bias": "MTF_BLOCK",
          "btc_guard": "BTC_GUARD",
          "circuit_breaker": "CB_LOCKED",
          "daily_bias": "REGIME",
      }.get(filter_name, "LOW_SCORE")
  ```
- **Test:** Unit test với mock filter that blocks → verify `audit:pending_snapshots` có entry với đúng `blocking_reason`. Unit test với normal scoring cycle → verify entry có `signal_result` và `final_score` đúng.

---

## TASK-29 — Tạo `AuditClient` (`backend-workspace/audit/client.py`)

- **Status:** TODO
- **Files:** `workspace/backend-workspace/audit/client.py` (file mới), `workspace/backend-workspace/audit/__init__.py` (file mới)
- **Vấn đề:** Chưa có `audit/` package trong `backend-workspace`. `AuditClient` là lightweight wrapper để `ScoringService` và `TradeExecutor` emit events mà không phụ thuộc trực tiếp vào Redis key string.
- **Phụ thuộc:** TASK-28 (Redis key `audit:pending_snapshots` đã được dùng ở TASK-28, AuditClient chỉ là wrapper cho consistency)
- **Fix:** Tạo `audit/client.py`:
  ```python
  # backend-workspace/audit/client.py
  import json
  import logging
  from typing import Optional

  logger = logging.getLogger(__name__)

  AUDIT_QUEUE_KEY = "audit:pending_snapshots"


  class AuditClient:
      """
      Lightweight Redis publisher for audit events.
      All methods are fire-and-forget — never raise exceptions to callers.
      """

      def __init__(self, redis_client, enabled: bool = True) -> None:
          self._r = redis_client
          self._enabled = enabled

      def emit(self, event_type: str, payload: dict) -> None:
          if not self._enabled:
              return
          try:
              self._r.rpush(AUDIT_QUEUE_KEY, json.dumps({"type": event_type, **payload}))
          except Exception as exc:
              logger.warning("AuditClient emit failed [%s]: %s", event_type, exc)

      def emit_trade_opened(self, signal_id: Optional[str], order_id: str,
                            symbol: str, direction: str, entry_price: float,
                            amount: float, leverage: int,
                            sl: float, tp1: float, tp2: Optional[float]) -> None:
          self.emit("trade_opened", {
              "signal_id": signal_id, "order_id": order_id,
              "symbol": symbol, "direction": direction,
              "entry_price": entry_price, "amount": amount, "leverage": leverage,
              "sl": sl, "tp1": tp1, "tp2": tp2,
          })

      def emit_trade_closed(self, order_id: str, exit_price: float,
                            exit_reason: str) -> None:
          self.emit("trade_closed", {
              "order_id": order_id,
              "exit_price": exit_price,
              "exit_reason": exit_reason,
          })
  ```
- **Test:** Unit test verify `emit()` pushes JSON to Redis key. Verify không raise exception khi Redis unavailable.

---

## TASK-30 — Wire `AUDIT_ENABLED` config + inject `AuditClient` vào `ScoringService`

- **Status:** TODO
- **Files:** `workspace/backend-workspace/engine/scoring_service.py`, `workspace/backend-workspace/config/` (config.yaml schema), `workspace/backend-workspace/main.py` (hoặc app entry point)
- **Vấn đề:** `ScoringService._audit_enabled` ở TASK-28 dùng `getattr(self, "_audit_enabled", False)` — chưa được set từ config. Cần wiring hoàn chỉnh để enable/disable không cần restart.
- **Phụ thuộc:** TASK-28, TASK-29
- **Fix:**
  - Thêm `audit.enabled: bool` vào `config.yaml` (default `false`)
  - Update `ScoringService.__init__()`:
    ```python
    def __init__(self, config=None, audit_client=None) -> None:
        self._config = config
        self._audit_client = audit_client
        self._audit_enabled = audit_client is not None
        ...
    ```
  - Tại app startup (main.py), inject khi `AUDIT_ENABLED=true`:
    ```python
    audit_client = None
    if config.get("audit", {}).get("enabled", False):
        from audit.client import AuditClient
        audit_client = AuditClient(redis_client=get_redis(), enabled=True)

    scoring_service = ScoringService(config=config, audit_client=audit_client)
    ```
  - Update `_emit_audit()` trong `ScoringService` để dùng `self._audit_client.emit(...)` nếu có, fallback về raw Redis push nếu không:
    ```python
    def _emit_audit(self, audit_data: dict) -> None:
        if self._audit_client:
            self._audit_client.emit("signal_snapshot", audit_data)
        elif self._audit_enabled:
            # fallback: direct Redis push (set bởi TASK-28)
            ...
    ```
- **Test:** Integration test: khởi tạo `ScoringService` với mock `AuditClient`, trigger một cycle, verify `emit()` được gọi đúng payload. Verify khi `audit_client=None` → không có Redis calls nào liên quan đến audit.

---

---

## TASK-31 — Tạo `MockExchangeHttpClient` + config injection

- **Status:** TODO
- **Files:**
  - `workspace/backend-workspace/exchange/mock_http_client.py` (file mới)
  - `workspace/backend-workspace/exchange/__init__.py` (file mới nếu chưa có)
  - `workspace/backend-workspace/config.yaml` — thêm `mock_exchange` section
  - `workspace/backend-workspace/main.py` (hoặc app entry point) — injection logic
- **Vấn đề:** Sau khi TASK-26 refactor `TradeExecutor` dùng `ExchangeInterface`, cần một concrete implementation chạy trong `backend-workspace` đóng vai trò HTTP client tới `mock-exchange-workspace`. Thiếu component này thì mock mode không thể hoạt động.
- **Phụ thuộc:** TASK-26 (TradeExecutor đã dùng ExchangeInterface)
- **Fix:**

  **1. Tạo `MockExchangeHttpClient`:**
  ```python
  # backend-workspace/exchange/mock_http_client.py
  import httpx
  from trading_core.exchange.interface import (
      ExchangeInterface, Order, Position, AccountState, OrderSide, OrderType
  )

  class MockExchangeHttpClient(ExchangeInterface):
      """HTTP adapter: translates ExchangeInterface calls to REST requests."""
      is_mock = True
      exchange_name = "mock_http"

      def __init__(self, base_url: str, timeout: float = 5.0) -> None:
          self._base_url = base_url.rstrip("/")
          self._client = httpx.AsyncClient(timeout=timeout)

      async def create_order(self, symbol, side, order_type, amount, price,
                             client_order_id=None, metadata=None) -> Order:
          resp = await self._client.post(
              f"{self._base_url}/exchange/orders",
              json={
                  "symbol": symbol,
                  "side": side.value,
                  "order_type": order_type.value,
                  "amount": amount,
                  "price": price,
                  "client_order_id": client_order_id,
              }
          )
          resp.raise_for_status()
          return Order(**resp.json())

      async def cancel_order(self, order_id: str, symbol: str) -> bool:
          resp = await self._client.delete(
              f"{self._base_url}/exchange/orders/{order_id}",
              params={"symbol": symbol},
          )
          resp.raise_for_status()
          return resp.json().get("cancelled", False)

      async def get_order(self, order_id, symbol):
          resp = await self._client.get(f"{self._base_url}/exchange/orders/{order_id}")
          resp.raise_for_status()
          return Order(**resp.json())

      async def get_open_orders(self, symbol=None):
          params = {"symbol": symbol} if symbol else {}
          resp = await self._client.get(f"{self._base_url}/exchange/orders", params=params)
          resp.raise_for_status()
          return [Order(**o) for o in resp.json()]

      async def get_position(self, symbol):
          resp = await self._client.get(f"{self._base_url}/exchange/positions/{symbol}")
          if resp.status_code == 404:
              return None
          resp.raise_for_status()
          return Position(**resp.json())

      async def get_all_positions(self):
          resp = await self._client.get(f"{self._base_url}/exchange/positions")
          resp.raise_for_status()
          return [Position(**p) for p in resp.json()]

      async def get_account_state(self):
          resp = await self._client.get(f"{self._base_url}/exchange/account")
          resp.raise_for_status()
          return AccountState(**resp.json())

      async def get_current_price(self, symbol) -> float:
          resp = await self._client.get(f"{self._base_url}/exchange/price/{symbol}")
          resp.raise_for_status()
          return float(resp.json()["price"])
  ```

  **2. Thêm section vào `config.yaml`:**
  ```yaml
  mock_exchange:
    enabled: false          # true = inject MockExchangeHttpClient, false = ccxt live/testnet
    url: "http://localhost:8001"
    timeout_seconds: 5
  ```

  **3. Injection tại app startup (`main.py`):**
  ```python
  mock_cfg = config.get("mock_exchange", {})
  if mock_cfg.get("enabled", False):
      from exchange.mock_http_client import MockExchangeHttpClient
      exchange = MockExchangeHttpClient(
          base_url=mock_cfg["url"],
          timeout=mock_cfg.get("timeout_seconds", 5),
      )
      logger.info("Mock exchange mode: routing orders to %s", mock_cfg["url"])
  else:
      exchange = build_ccxt_exchange(config)  # existing logic

  trade_executor = TradeExecutor(exchange=exchange, config=config)
  ```

- **Test:**
  - Unit test: mock `httpx.AsyncClient`, verify `create_order()` gọi đúng URL, method, và payload
  - Unit test: verify `raise_for_status()` propagates lên `TradeExecutor` khi mock-exchange trả về 500
  - Integration note: cần mock-exchange-workspace đang chạy để test end-to-end

---

## Tracking

| Task | Status | Phụ thuộc | Ghi chú |
|------|--------|-----------|---------|
| TASK-26 | DONE | — | Refactor TradeExecutor; cần TASK-31 để chạy mock mode |
| TASK-27 | DONE | — | Blocking cho audit link |
| TASK-28 | DONE | TASK-27 | Cần signal_id từ _persist_signal() |
| TASK-29 | DONE | TASK-28 | Wrapper AuditClient |
| TASK-30 | DONE | TASK-28, TASK-29 | Wire hoàn chỉnh trước khi bật audit |
| TASK-31 | DONE | TASK-26 | Blocking cho mock mode end-to-end |

**Hoàn thành TASK-26 → TASK-31 = sẵn sàng implement `mock-exchange-workspace`.**
