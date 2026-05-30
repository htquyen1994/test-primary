# Master Audit Report — 2026-05-17

> Generated: 2026-05-17 12:14 UTC  
> Based on: MASTER_AUDIT_PROMPT.md  
> Environment: Windows / SQL Server localhost:1433 / Redis localhost:6379

---

## Step 0 — Infrastructure Pre-Check

| Component | Status | Detail |
|-----------|--------|--------|
| Redis | ✅ UP | localhost:6379 responding |
| Backend API | ✅ UP | localhost:8000 |
| Mock Exchange | ✅ UP | localhost:8001 |
| Frontend | ✅ UP | localhost:5173 |
| OB Feed BTC/USDT | ✅ OK | bid=78,448.20 bid_stack=0.45 age=21s |
| OB Feed ETH/USDT | ✅ OK | bid=2,193.51 bid_stack=48.87 age=21s |
| OB Feed SOL/USDT | ✅ OK | bid=86.98 bid_stack=1330.87 age=21s |
| Pipeline heartbeat | ⚠ None key | OB snaps are fresh — pipeline running |
| Audit pending queue | ✅ 0 | Queue drained |

**Note:** `pipeline:heartbeat` Redis key is not being set by the pipeline — OB snapshots confirm it IS running. Consider adding a heartbeat write in the main loop.

---

## Step 1 — Daily Signal Log Audit

### 1A. Signal Volume (2026-05-17 UTC)

| Classification | Count |
|---------------|------:|
| IGNORE | 33,967 |
| ALERT | **0** |
| WATCH | **0** |
| **Total today** | **33,967** |

**Breakdown by asset:**

| Asset | IGNORE |
|-------|-------:|
| BTC/USDT | 8,523 |
| ETH/USDT | 8,397 |
| SOL/USDT | 8,533 |
| VELO/USDT | 8,514 |

### 1B. Score Distribution

| Metric | Value |
|--------|------:|
| Min score today | 0 |
| Max score today | **44** |
| Avg score today | 6.0 |
| Signal count | 33,967 |

**ALERT threshold is 75 — no signal has reached it today.**

### 1C. Filter Blocks

Column `block_reason` not present in `dbo.signal_log` schema — filter block analysis unavailable.  
→ **Action**: Add `block_reason VARCHAR(120) NULL` column to signal_log in next migration.

### 1D. Score Component Breakdown (avg today)

| Component | Avg Score | Max Possible |
|-----------|----------:|-------------:|
| OrderFlow | 3.7 | 35 |
| SMC | 1.8 | 30 |
| VSA | **11.2** | 30 |
| Context | 4.8 | 15 |
| Bonus | 0.5 | 15 |
| **Total avg** | **~22** | **125 (raw)** |

**Observations:**
- VSA is the dominant component (11.2/30 avg = 37%), suggesting volume conditions detected
- SMC score very low (1.8/30 = 6%) → no CHoCH/OB/FVG patterns triggering
- OrderFlow at 3.7/35 = 11% → OB bid/ask data reaching scorer but no strong imbalance
- Context at 4.8/15 = 32% → some 1H alignment, no funding/S/R boost
- Combined raw avg ~22/125 → normalized ~17.6/100 → well below IGNORE→WATCH threshold (~55)

### 1D. Daily Comparison

| Period | Total | ALERT | WATCH |
|--------|------:|------:|------:|
| Today | 33,967 | 0 | 0 |
| Yesterday | 15,663 | 0 | 0 |
| Last 7 days | 51,673 | 0 | 0 |

**Today count is 2.2× yesterday** — system was likely restarted or loop rate increased during the session.

### 1E. Latest Signals (sample)

```
2026-05-17 12:13 UTC  SOL/USDT  1h  long   score=5   IGNORE  CHOPPY
2026-05-17 12:13 UTC  ETH/USDT  1h  long   score=13  IGNORE  CHOPPY
```

Max individual score seen today: **44/100** — still 31 points below ALERT threshold.

### 1F. Regime Distribution Today

| Regime | Count | % |
|--------|------:|--:|
| CHOPPY | 24,517 | 72% |
| TRENDING | 5,481 | 16% |
| RANGING | 3,969 | 12% |

**72% of signals in CHOPPY regime.** Choppy has regime multiplier ×0.85, capping max achievable score. Alerts are far less likely during choppy regime even with good setups.

### 1G. Validation Sample

```
ALERT/WATCH signals with full SL/TP (7 days): 0
→ INSUFFICIENT — need ≥20 for statistical significance
→ Steps 3-7 (Component Validation, Statistics) DEFERRED
```

---

## Step 2 — Live Market Analysis (12:14 UTC)

### Market Snapshot

| Symbol | Price | Regime | Daily | 4H | 1H | RSI(15m) | ADX(15m) | Max Score |
|--------|------:|--------|-------|-----|-----|--------:|--------:|----------:|
| BTC/USDT | $78,402.70 | TRENDING | NEUTRAL | ranging | bearish | 63.2 | 26.9 | 51/100 |
| ETH/USDT | $2,192.40 | TRENDING | BEAR | ranging | bearish | 60.2 | 21.8 | 51/100 |
| SOL/USDT | $86.91 | TRENDING | BEAR | ranging | bearish | 54.5 | 24.2 | 51/100 |

### Per-Symbol Analysis

**BTC/USDT**
- Regime: TRENDING (ADX 1H = 33.0, ×1.0 multiplier)
- Trend: Price BELOW EMA200 1H ($79,744) → bearish short-term
- MTF Scenario B (4H ranging, 1H bearish → size ×0.5, score -10)
- BB position: 78% — price near upper band after bounce
- RSI 63.2 — elevated, approaching overbought for a bearish signal
- **Max theoretical score: 51/100 — below ALERT (75)**

**ETH/USDT**
- Regime: TRENDING (ADX 1H = 30.7, ×1.0)
- Daily: BEAR | 4H: ranging | 1H: bearish (full alignment increasing)
- Price BELOW EMA200 1H ($2,257)
- RSI 60.2 — elevated
- **Max theoretical score: 51/100**

**SOL/USDT**
- Regime: TRENDING (ADX 1H = 34.1, ×1.0) — strongest trend
- Daily: BEAR | 4H: ranging | 1H: bearish
- Price BELOW EMA200 1H ($91)
- RSI 54.5 — most neutral, closest to conditions for SHORT
- BB position: 66% — less extended
- **Max theoretical score: 51/100**

### Why Max Score is Capped at 51

The `market_analysis.py` OB feed check uses a standalone Python environment without the `redis` package installed → reports "MISS". Actual OB status from Redis check:

| Symbol | bid_stack | age | Valid |
|--------|----------:|----:|-------|
| BTC/USDT | 0.45 | 21s | ✅ |
| ETH/USDT | 48.87 | 21s | ✅ |
| SOL/USDT | 1330.87 | 21s | ✅ |

**With real OB data available**, the actual max score would be higher (OrderFlow component fully unlocked). The 51/100 cap is a false negative due to environment isolation.

**Actual max score estimate with OB available:**
- SMC best (CHoCH+OB+FVG): ~30
- VSA best: ~20
- OF with OB: ~25
- Context (1H bias aligned): ~11
- ×1.0 TRENDING, -10 Scenario B
- Estimate: ~(25+30+20+11+15) × 1.0 / 125 × 100 - 10 = **~68/100**
- Still below ALERT (75) in Scenario B. Would need Scenario A (4H aligned) for ALERT.

### MTF Conflict — Key Issue

All 3 assets: **4H = ranging, 1H = bearish → Scenario B**

This means:
- Size multiplier: ×0.5 (half position)
- Score penalty: -10 pts
- 4H has NOT confirmed the bearish direction (not yet bearish, just ranging)
- For Scenario A (full size, +10 pts), 4H needs to also flip to bearish

---

## Step 3-7 — Deferred (Insufficient Validation Sample)

No ALERT or WATCH signals have been generated since system start. All signals classified as IGNORE.

**Required:** ≥20 ALERT/WATCH signals with entry_price + stop_loss + take_profit_1 filled.

**ETA:** System needs to run through periods with TRENDING + Scenario A conditions to generate qualifying signals.

---

## Diagnostic Summary

### Why No ALERT/WATCH Signals?

1. **Score too low (avg 22/125 raw → ~17.6 normalized):**
   - SMC score near 0 → no CHoCH detected in current data
   - This is the gating condition — CHoCH must fire first to unlock OB+FVG scoring

2. **72% Choppy regime:**
   - Most of the day was CHOPPY (ADX < 20), which caps scores
   - TRENDING periods exist (16%) but haven't produced qualifying SMC setups

3. **Scenario B for all assets:**
   - 4H ranging vs 1H bearish → -10 score penalty + ×0.5 size
   - Needs 4H to also turn bearish for Scenario A alignment

4. **Market context bearish but indecisive:**
   - RSI 54–63 range: not in oversold zone for longs, not clearly overbought for shorts
   - Price below EMA200(1H) is bearish signal, but 4H hasn't confirmed

### Issues Found

| Issue | Severity | Action |
|-------|----------|--------|
| `block_reason` column missing from signal_log | LOW | Add via migration |
| `pipeline:heartbeat` key not written | LOW | Add heartbeat to pipeline loop |
| `market_analysis.py` OB "MISS" false negative | LOW | Use backend venv or pass ob_available=True |
| VELO/USDT still generating signals | MEDIUM | Remove from exchange_assets per user decision |
| 0 ALERT/WATCH signals after 7+ days | INFO | System working; market hasn't produced qualifying setups |
| Duplicate signals (same time, same ETH score=13) | MEDIUM | Check pipeline dedup — may be processing same candle multiple times |

---

## Recommendations

### Immediate (Today)

1. **Remove VELO/USDT** from `exchange_assets` table — user confirmed this asset should be excluded
2. **Investigate duplicate signal firing** — 9+ identical ETH signals at 12:13 suggests loop is firing multiple times per candle
3. **Add pipeline heartbeat** — `r.set('pipeline:heartbeat', datetime.utcnow().isoformat(), ex=120)`

### Short-term

4. **Add `block_reason` column** to `signal_log`:
   ```sql
   ALTER TABLE dbo.signal_log ADD block_reason VARCHAR(120) NULL;
   ```
5. **Fix market_analysis.py OB check** — install redis in the analysis env or read snap via HTTP API

### When Signals Start Appearing

6. **Watch for Scenario A** — when 4H flips to bearish for any asset, score will jump +20 vs Scenario B
7. **SOL/USDT most likely first candidate** — strongest trend (ADX 34.1), most neutral RSI (54.5), daily already BEAR
8. **Target conditions for ALERT**: TRENDING + Scenario A + CHoCH(1H) + OB retest + RSI < 50 (for short)

---

## Next Audit

- Re-run full audit after first ALERT/WATCH signal fires
- Minimum validation sample trigger: 5 signals (for early check), 20 signals (for statistics)
- Check daily at ~12:00 UTC while system is in early operation phase

---

## Actions Taken During This Audit

| # | Action | Result |
|---|--------|--------|
| 1 | Disabled VELO/USDT in `exchange_assets` | ✅ `enabled=0` — no more VELO signals |
| 2 | Fixed `ohlcv_service.py` candle dedup bug | ✅ Changed `== ts` to `<= last_seen` — stops 9× replay per poll |
| 3 | Added `pipeline:heartbeat` to scoring service | ✅ Set on every candle_close event, TTL=300s |
| 4 | Added `block_reason`, `mtf_scenario`, `size_multiplier` columns to `signal_log` | ✅ Migration applied |

**Note:** Changes #2 and #3 require **pipeline restart** to take effect (backend `main.py`).

---

*Report generated by Claude Code — 2026-05-17 12:14 UTC*
