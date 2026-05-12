# Prompt: Tạo Bộ Tài Liệu Hệ Thống Chi Tiết — Crypto Trading System

> **Mục đích:** Prompt này dùng để yêu cầu AI tạo ra bộ tài liệu kỹ thuật đầy đủ cho hệ thống Crypto Trading System, bao gồm mô tả hệ thống, diagrams, database design, và tất cả những gì cần thiết để một AI engineer có thể hiểu rõ toàn bộ hệ thống.
>
> **Cách dùng:** Copy toàn bộ prompt bên dưới và paste vào AI (Claude, GPT-4, Gemini...). Cung cấp thêm source code hoặc file context nếu cần.

---

## PROMPT

```
Bạn là một Senior AI Engineer và System Architect với 10+ năm kinh nghiệm thiết kế hệ thống trading. 
Nhiệm vụ của bạn là tạo ra bộ tài liệu kỹ thuật TOÀN DIỆN cho hệ thống Crypto Trading System 
được mô tả dưới đây.

---

## CONTEXT: HỆ THỐNG CẦN TÀI LIỆU HÓA

### Tổng quan hệ thống
Đây là một Semi-Automatic Crypto Futures Trading Platform với kiến trúc 3 lớp:
- Layer 1 — Data Input: Thu thập OHLCV, Order Book, Funding Rate từ sàn giao dịch
- Layer 2 — AI Engine: Phân tích tín hiệu, chấm điểm, quản lý rủi ro
- Layer 3 — Human Confirm Dashboard: Giao diện xác nhận lệnh cho trader

### Tech Stack
- Backend: Python (asyncio + threading), FastAPI, Redis, SQLite/PostgreSQL
- Frontend: React
- Data: ccxt library (REST polling), Redis pub/sub
- Deployment: Docker (Redis), local Python processes

### Các module chính
1. Data Pipeline: OHLCVService, OrderBookService, DeltaService, FundingService
2. AI Engine: ScoringService, RegimeDetector, MTFBiasDetector, BTCVolatilityGuard
3. Signal Scoring: OrderFlowAnalysis (35pts), SMCAnalysis (30pts), VSA+VolumeProfile (30pts), ContextFilter (15pts), ConfluenceBonus (15pts)
4. Risk Management: CircuitBreaker (4 triggers), RiskManager, CorrelationManager
5. API Layer: FastAPI với REST + WebSocket endpoints
6. Storage: Redis (buffer/cache), SQL (persistent: signal_log, trade_journal, backtest_results, circuit_breaker_state)

### Scoring Formula
raw = OrderFlow(0-35) + SMC(0-30) + VSA(0-30) + Context(0-15) + Bonus(0-15)
final = min(round(raw × regime_multiplier / 125 × 100), 100)
Phase 9 adjustments: ±10 pts MTF, cap ≤60 nếu không có Order Book

### Circuit Breaker (4 triggers)
- Trigger 1: 3 consecutive losses in 24h → lock 12h
- Trigger 2: Single loss > 4% equity → lock 6h  
- Trigger 3: Daily loss > 5% equity → lock until 00:00 UTC
- Trigger 4: Drawdown > 10% from 7-day peak → lock 24h + manual review

---

## YÊU CẦU TÀI LIỆU

Hãy tạo ra BỘ TÀI LIỆU ĐẦY ĐỦ gồm các phần sau. Với mỗi phần, hãy đi vào CHI TIẾT TỐI ĐA:

---

### PHẦN 1: SYSTEM OVERVIEW DOCUMENT

Tạo tài liệu tổng quan hệ thống bao gồm:

1.1 **Executive Summary** (1 trang)
- Mục đích hệ thống, vấn đề giải quyết
- Các tính năng cốt lõi
- Giới hạn và phạm vi

1.2 **System Context Diagram** (C4 Level 1)
- Vẽ diagram dạng text/ASCII hoặc Mermaid
- Thể hiện: hệ thống, người dùng, external systems (Exchange APIs, Database)
- Mô tả từng mối quan hệ

1.3 **High-Level Architecture Diagram** (C4 Level 2)
- Vẽ diagram thể hiện 3 layers + Redis + Database
- Mũi tên thể hiện data flow
- Ghi chú protocol (REST, WebSocket, pub/sub, SQL)

1.4 **Component Inventory Table**
Bảng liệt kê TẤT CẢ components với:
| Component | Module/File | Responsibility | Input | Output | Dependencies |
Bao gồm: OHLCVService, OrderBookService, DeltaService, FundingService, ScoringService, RegimeDetector, MTFBiasDetector, BTCVolatilityGuard, SignalScorer, OrderFlowAnalysis, SMCAnalysis, VSAModule, ContextFilter, ConfluenceBonus, CircuitBreaker, RiskManager, CorrelationManager, AlertBuilder, TradeExecutor, FastAPI Backend, React Frontend

---

### PHẦN 2: DETAILED SERVICE DOCUMENTATION

Với MỖI service/module, tạo tài liệu chi tiết theo template:

```
## [Tên Service]

### Mục đích
[Mô tả ngắn gọn service làm gì]

### Vị trí trong hệ thống
[File path, layer, dependencies]

### Đối tượng/Class chính
[Tên class, constructor params, attributes]

### Phương thức công khai
| Method | Input | Output | Side Effects | Description |
|--------|-------|--------|--------------|-------------|

### Data Flow
[Mô tả dữ liệu vào/ra, format, validation]

### Error Handling
[Các loại lỗi, retry logic, fallback behavior]

### Configuration
[Các tham số config liên quan từ config.yaml]

### Redis Keys
[Các key Redis service này đọc/ghi]

### Sequence Diagram
[Mermaid sequence diagram cho flow chính]
```

Áp dụng template trên cho TẤT CẢ các services sau:

**Data Layer:**
- OHLCVService (data/ohlcv_service.py)
- OrderBookService (data/orderbook_service.py)  
- DeltaService (data/delta_service.py)
- FundingService (data/funding.py)

**Engine Layer:**
- ScoringService (engine/scoring_service.py) — orchestrator chính
- RegimeDetector (engine/regime_detector.py)
- MTFBiasDetector (engine/mtf_bias.py)
- BTCVolatilityGuard (engine/btc_guard.py)
- SignalScorer (engine/scorer.py)
- OrderFlowAnalysis (engine/order_flow.py)
- SMCAnalysis (engine/smc.py)
- VSAModule (engine/vsa.py + engine/volume_profile.py)
- ContextFilter (engine/context.py)
- ConfluenceBonus (engine/confluence.py)
- CorrelationManager (engine/correlation_manager.py)

**Risk Layer:**
- CircuitBreaker (risk/circuit_breaker.py)
- RiskManager (risk/manager.py)

**API Layer:**
- FastAPI Backend (api/main.py)
- TradeExecutor (trade/executor.py)

---

### PHẦN 3: DATA FLOW DIAGRAMS

3.1 **Realtime Signal Flow** (end-to-end)
Vẽ Mermaid sequence diagram chi tiết từ:
Exchange → OHLCVService → Redis → ScoringService → [Filters] → Scoring → Risk Check → Alert → FastAPI → WebSocket → React Dashboard → User Action → TradeExecutor → Exchange

3.2 **Candle Close Trigger Flow**
Sequence diagram: candle_close pub/sub → ScoringService.run_scoring() → tất cả các bước xử lý

3.3 **Circuit Breaker State Machine**
Mermaid stateDiagram-v2 với:
- States: UNLOCKED, LOCKED, PENDING_REVIEW
- Transitions: 4 triggers, smart unlock, manual unlock, extend
- Guards: regime check, review note validation

3.4 **MTF Bias Decision Tree**
Mermaid flowchart với:
- Input: 4H bias, 1H bias, signal direction
- Decision nodes: Scenario A/B/C
- Output: size multiplier, score adjustment, BLOCK

3.5 **Trade Execution Flow**
Sequence diagram: User CONFIRM → API → CircuitBreaker check → TradeExecutor → ccxt → Exchange → SL/TP placement → Journal

3.6 **Backtest Flow**
Flowchart: config → load historical data → candle loop → scoring simulation → metrics → walk-forward → AI feedback

---

### PHẦN 4: DATABASE DESIGN DOCUMENT

4.1 **Entity Relationship Diagram (ERD)**
Vẽ Mermaid erDiagram với TẤT CẢ tables:
- signal_log
- trade_journal  
- backtest_results
- circuit_breaker_state
Thể hiện relationships, foreign keys, cardinality

4.2 **Table Specifications** — Với MỖI table:
```
### Table: [table_name]

**Mục đích:** [Lưu trữ gì, ai đọc/ghi]

**Schema:**
| Column | Type | Constraints | Description | Example |
|--------|------|-------------|-------------|---------|

**Indexes:**
| Index Name | Columns | Type | Purpose |
|------------|---------|------|---------|

**Relationships:**
[FK references, join patterns]

**Query Patterns:**
[Các query phổ biến nhất, với SQL example]

**Data Volume:**
[Ước tính rows/day, retention policy]
```

4.3 **Redis Key Catalog**
Bảng đầy đủ TẤT CẢ Redis keys:
| Key Pattern | Type | TTL | Format | Writer | Readers | Description |
|-------------|------|-----|--------|--------|---------|-------------|

Bao gồm:
- ohlcv:{sym}:{tf} — ring buffer
- delta:{sym}:5m — cumulative delta
- ob:{sym}:snap — order book snapshot
- funding:{sym} — funding rate
- poc:{sym} — Point of Control
- regime:{sym} — market regime
- delta_history:{sym} — 24h delta history
- daily_bias:{sym} — Daily bias (TTL 4h)
- btc_guard:spike — BTC spike state
- circuit_breaker:locked — fast-path cache
- circuit_breaker:recent_losses — consecutive loss tracking
- circuit_breaker:7day_peak — equity peak cache

4.4 **Pub/Sub Channel Catalog**
| Channel | Publisher | Subscribers | Message Format | Trigger |
|---------|-----------|-------------|----------------|---------|

Bao gồm: candle_close, alerts:channel, logs:channel, cancel_all_alerts, btc_spike, circuit_breaker:events

---

### PHẦN 5: API DOCUMENTATION

5.1 **API Overview**
- Base URL, authentication, versioning
- Common response formats, error codes
- Rate limiting

5.2 **WebSocket Endpoints**
Với mỗi WS endpoint:
```
### WS /ws/[endpoint]

**Mục đích:** [Mô tả]
**Message Format:** [JSON schema]
**Trigger:** [Khi nào message được gửi]
**Example Message:**
```json
{ ... }
```
```

Endpoints: /ws/alerts, /ws/logs, /ws/portfolio

5.3 **REST Endpoints**
Với mỗi REST endpoint:
```
### [METHOD] /api/[path]

**Mục đích:** [Mô tả]
**Request:**
  - Headers: [required headers]
  - Path params: [nếu có]
  - Query params: [nếu có]
  - Body: [JSON schema]
**Response:**
  - 200: [schema + example]
  - 4xx/5xx: [error cases]
**Side Effects:** [DB writes, Redis updates, external calls]
**Circuit Breaker:** [HTTP 423 nếu locked]
```

Endpoints cần document:
- GET /api/signals
- POST /api/signals/{id}/confirm
- POST /api/signals/{id}/skip
- PATCH /api/signals/{id}/expire
- GET /api/journal
- GET /api/analytics
- GET /api/portfolio
- GET /api/config
- POST /api/config/reload
- GET /api/config/exchange
- PUT /api/config/exchange
- GET /api/config/trading
- PUT /api/config/trading
- GET /api/config/trading/history
- GET /api/circuit-breaker/status
- POST /api/circuit-breaker/unlock
- GET /api/backtest/results
- POST /api/backtest/run

---

### PHẦN 6: OBJECT MODEL DOCUMENTATION

6.1 **Core Domain Objects**
Với MỖI domain object/dataclass, tạo tài liệu:
```
### [ClassName]

**File:** [path]
**Type:** [dataclass/class/Pydantic model]
**Mục đích:** [Mô tả]

**Fields:**
| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|

**Lifecycle:**
[Ai tạo, ai đọc, ai modify, khi nào bị destroy]

**Serialization:**
[JSON schema nếu được serialize]
```

Objects cần document:
- Signal (strategies/base.py)
- TradeResult (backtest/models.py)
- OrderFlowResult (engine/order_flow.py)
- ContextResult (engine/context.py)
- LockInfo (risk/circuit_breaker.py)
- SignalCard (alert/builder.py)
- RegimeState
- MTFAlignment
- BTCSpikeState

6.2 **Abstract Interfaces**
Document TẤT CẢ abstract base classes:
- BaseStrategy: generate_signals() contract
- BaseIndicator: compute() contract
- Mô tả invariants, pre/post conditions

6.3 **Configuration Object Model**
Mô tả đầy đủ config.yaml schema:
- Tất cả namespaces (account, position, regime, risk, strategy, exchange, assets, backtest, logging)
- Với mỗi field: type, default, valid range, description, ảnh hưởng đến module nào

---

### PHẦN 7: SCORING ALGORITHM DEEP DIVE

7.1 **Scoring Pipeline Flowchart**
Mermaid flowchart chi tiết từng bước:
[1] Regime Detection → [2] MTF Bias Filter → [3] BTC Spike Guard → [4] Circuit Breaker → [5] Signal Scoring → [6] Risk Manager → [7] Publish

7.2 **Module Scoring Specifications**
Với MỖI scoring module, tạo bảng chi tiết:
```
### Module: [Tên] (max [N] pts)

**Mục đích:** [Mô tả]

**Scoring Rules:**
| Condition | Points | Implementation | Notes |
|-----------|--------|----------------|-------|

**Pseudocode:**
```python
def compute_[module]_score(...) -> float:
    score = 0
    # condition 1
    if ...: score += N
    # condition 2
    if ...: score += N
    return min(score, MAX)
```

**Edge Cases:**
- [Điều kiện đặc biệt và cách xử lý]

**Data Dependencies:**
- [Cần dữ liệu gì từ Redis/DB]
```

Modules: OrderFlow, SMC, VSA+VolumeProfile, ContextFilter, ConfluenceBonus

7.3 **Normalization Formula**
Giải thích chi tiết:
- raw score range (0-125)
- regime multiplier values và khi nào áp dụng
- MTF adjustment (+10/-10/BLOCK)
- Data quality cap (≤60)
- Final classification (ALERT/WATCH/IGNORE)

7.4 **Dynamic Delta Threshold**
Giải thích thuật toán:
- percentile_75(|delta_24h|) × 1.5
- Fallback logic
- Sanity bounds (100-50000)
- Tại sao dynamic tốt hơn static

---

### PHẦN 8: DEPLOYMENT & OPERATIONS GUIDE

8.1 **System Requirements**
- Hardware requirements (RAM, CPU, disk)
- Software dependencies (Python version, packages)
- External services (Redis, Exchange API access)

8.2 **Startup Sequence**
Mermaid sequence diagram: thứ tự khởi động các services
- Redis check
- DB connection + migrations
- Config validation
- OHLCVService seed (200 × 4H + 250 × Daily candles)
- ScoringService start
- FastAPI start
- Frontend start

8.3 **Configuration Reference**
Bảng đầy đủ tất cả config.yaml parameters:
| Parameter | Path | Type | Default | Valid Range | Description | Affects |
|-----------|------|------|---------|-------------|-------------|---------|

8.4 **Environment Variables**
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
Bao gồm: DATABASE_URL, ALLOWED_ORIGINS, REDIS_URL, ...

8.5 **Monitoring & Health Checks**
- Các metrics quan trọng cần monitor
- Log levels và ý nghĩa
- Cách detect khi system không hoạt động đúng

---

### PHẦN 9: KNOWN LIMITATIONS & DESIGN DECISIONS

9.1 **Current Limitations**
Bảng liệt kê các limitation đã biết:
| Limitation | Impact | Workaround | Future Fix |
|------------|--------|------------|------------|

Bao gồm:
- Order Book Feed chưa chạy → Order Flow score = 0 → score cap ≤60
- Trade Tape chưa chạy → Delta = 0
- WebSocket ingestion chưa implement (dùng REST polling)
- Testnet mode mặc định

9.2 **Design Decisions Log**
Với mỗi quyết định thiết kế quan trọng:
```
### Decision: [Tên]
**Context:** [Vấn đề cần giải quyết]
**Options Considered:** [Các lựa chọn đã xem xét]
**Decision:** [Lựa chọn cuối cùng]
**Rationale:** [Lý do]
**Trade-offs:** [Ưu/nhược điểm]
**Date:** [Khi nào quyết định]
```

Decisions cần document:
- REST polling vs WebSocket (Design Decision 9)
- asyncio + threading vs Celery
- SQLite vs PostgreSQL (DATABASE_URL switching)
- Redis as central buffer
- Semi-auto vs fully-auto trading
- Score cap khi OB unavailable
- Dynamic delta threshold

9.3 **Phase 9 Changes Summary**
Bảng tóm tắt tất cả thay đổi trong Phase 9 (v2.0):
| Change | Problem Solved | Implementation | Impact |
|--------|----------------|----------------|--------|

---

### PHẦN 10: GLOSSARY & REFERENCE

10.1 **Technical Glossary**
Định nghĩa đầy đủ TẤT CẢ thuật ngữ kỹ thuật:
- Trading terms: OHLCV, Order Block, FVG, CHoCH, SMC, VSA, POC, VAH, VAL, Funding Rate, Perpetual, Delta, Absorption, Regime, ATR, ADX, RSI, EMA, Fibonacci, Confluence Zone
- System terms: Signal, Score, Alert, Watch, Ignore, Circuit Breaker, Portfolio Heat, Correlated Risk, MTF Bias, BTC Spike Guard, Time Invalidation, Walk-Forward Analysis
- Technical terms: Redis pub/sub, asyncio, ccxt, Celery, FastAPI, WebSocket

10.2 **Abbreviations Table**
| Abbreviation | Full Form | Context |
|--------------|-----------|---------|

10.3 **File Structure Reference**
Cây thư mục đầy đủ với mô tả từng file:
```
backend-workspace/
├── main.py                    # [mô tả]
├── config.yaml                # [mô tả]
├── data/
│   ├── ohlcv_service.py       # [mô tả]
│   └── ...
├── engine/
│   ├── scoring_service.py     # [mô tả]
│   └── ...
...
```

---

## FORMAT YÊU CẦU

- Sử dụng Markdown với headers rõ ràng
- Tất cả diagrams dùng Mermaid syntax (có thể render trực tiếp)
- Tất cả code examples dùng Python syntax highlighting
- Tất cả JSON examples phải valid JSON
- Bảng phải có header row và alignment
- Mỗi phần phải có thể đọc độc lập (self-contained)
- Sử dụng tiếng Việt cho mô tả, tiếng Anh cho technical terms và code

## ĐỘ CHI TIẾT YÊU CẦU

- Không bỏ qua bất kỳ field nào trong dataclass/schema
- Không bỏ qua bất kỳ endpoint nào trong API
- Không bỏ qua bất kỳ Redis key nào
- Mỗi scoring condition phải có ví dụ cụ thể
- Mỗi diagram phải có chú thích đầy đủ
- Mỗi design decision phải có rationale rõ ràng

## OUTPUT

Tạo ra 10 file Markdown riêng biệt, mỗi file tương ứng với 1 phần ở trên:
- 01-system-overview.md
- 02-service-documentation.md
- 03-data-flow-diagrams.md
- 04-database-design.md
- 05-api-documentation.md
- 06-object-model.md
- 07-scoring-algorithm.md
- 08-deployment-operations.md
- 09-limitations-decisions.md
- 10-glossary-reference.md

Bắt đầu với file 01-system-overview.md và tiếp tục tuần tự.
```

---

## HƯỚNG DẪN SỬ DỤNG PROMPT

### Cách 1: Chạy toàn bộ một lần
Paste toàn bộ prompt vào AI với context source code. Phù hợp với AI có context window lớn (Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro).

### Cách 2: Chạy từng phần
Chạy từng PHẦN riêng biệt. Ví dụ:
```
[Paste context hệ thống]
Bây giờ hãy tạo PHẦN 4: DATABASE DESIGN DOCUMENT theo yêu cầu sau:
[Paste nội dung Phần 4]
```

### Cách 3: Iterative refinement
1. Chạy Phần 1 (System Overview) trước
2. Review và feedback
3. Chạy Phần 2 với context từ Phần 1
4. Tiếp tục...

### Context files nên cung cấp kèm
Khi chạy prompt, cung cấp thêm các file sau để AI có context chính xác:
- `.kiro/specs/crypto-trading-system/design.md`
- `.kiro/specs/crypto-trading-system/requirements.md`
- `project/design/BACKEND_ARCHITECTURE.md`
- `project/design/AI_Trade_Tool_Blueprint.md`
- `workspace/backend-workspace/engine/order_flow.py`
- `workspace/backend-workspace/engine/context.py`
- `workspace/backend-workspace/risk/circuit_breaker.py`
- `workspace/backend-workspace/api/main.py`
- `workspace/backend-workspace/main.py`

---

## PROMPT VARIANTS

### Variant A: Quick Overview (30 phút)
Dùng khi cần tài liệu nhanh, không cần chi tiết tối đa:
```
Dựa vào context hệ thống Crypto Trading System, hãy tạo:
1. System Architecture Diagram (Mermaid)
2. Component Inventory Table (tất cả services + responsibilities)
3. Data Flow Diagram (realtime signal flow)
4. Database ERD (4 tables)
5. Redis Key Catalog
6. API Endpoint List với mô tả ngắn

Format: Markdown, diagrams dùng Mermaid.
```

### Variant B: Deep Dive — Scoring System
Dùng khi cần hiểu chi tiết thuật toán scoring:
```
Hãy tạo tài liệu chi tiết về Signal Scoring System bao gồm:
1. Scoring Pipeline Flowchart (Mermaid, từng bước)
2. Module Specifications (OrderFlow/SMC/VSA/Context/Confluence)
3. Normalization Formula với ví dụ số cụ thể
4. Phase 9 Adjustments (MTF/BTC Guard/Data Quality Cap)
5. Classification Logic (ALERT/WATCH/IGNORE)
6. Edge Cases và cách xử lý
```

### Variant C: Database & Storage Focus
Dùng khi cần hiểu data layer:
```
Hãy tạo tài liệu đầy đủ về data storage layer:
1. ERD với tất cả tables và relationships
2. Table specs chi tiết (schema, indexes, query patterns)
3. Redis Key Catalog đầy đủ (key, type, TTL, format, writer, readers)
4. Pub/Sub Channel Catalog
5. Data retention và volume estimates
6. Migration strategy
```

### Variant D: Operations Guide
Dùng khi cần deploy/operate hệ thống:
```
Hãy tạo Operations Guide cho Crypto Trading System:
1. Startup sequence (thứ tự khởi động services)
2. Configuration reference (tất cả config.yaml params)
3. Environment variables
4. Health check endpoints
5. Common issues và troubleshooting
6. Monitoring metrics
```

---

## CHECKLIST SAU KHI NHẬN TÀI LIỆU

Sau khi AI tạo xong tài liệu, kiểm tra:

- [ ] Tất cả 10 phần đã được tạo
- [ ] Mermaid diagrams có thể render (test tại mermaid.live)
- [ ] Tất cả Redis keys đã được liệt kê (so sánh với BACKEND_ARCHITECTURE.md)
- [ ] Tất cả API endpoints đã được document
- [ ] Scoring formula khớp với code thực tế
- [ ] Circuit Breaker 4 triggers đã được mô tả đúng
- [ ] Phase 9 changes đã được phản ánh
- [ ] Glossary đầy đủ các thuật ngữ trading + technical
- [ ] Known limitations đã được liệt kê (OB/Trade Tape chưa chạy)
- [ ] Design decisions có rationale rõ ràng
