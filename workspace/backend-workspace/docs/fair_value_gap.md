# Strategy Spec: Fair Value Gap (FVG)

## Glossary
- **FVG**: Three-candle imbalance where the wicks of candle[i-2] and candle[i] do not overlap.
- **Bullish FVG**: candle[i-2].high < candle[i].low — gap above.
- **Bearish FVG**: candle[i-2].low > candle[i].high — gap below.
- **Midpoint**: (top + bot) / 2 of the gap.
- **Filled**: FVG is filled when price trades through the full gap.

## Mathematical Logic
```
Bullish FVG: candle[i-2].high < candle[i].low
  top = candle[i].low
  bot = candle[i-2].high
  mid = (top + bot) / 2

Bearish FVG: candle[i-2].low > candle[i].high
  top = candle[i-2].low
  bot = candle[i].high
  mid = (top + bot) / 2

Midpoint touch: abs(current_price - mid) / mid <= 0.001 (0.1% tolerance)
Filled: Bullish FVG → candle.low <= bot; Bearish FVG → candle.high >= top
```

## Objective Entry/Exit
| | Long | Short |
|---|---|---|
| **Trigger** | Price touches bullish FVG midpoint | Price touches bearish FVG midpoint |
| **Entry** | Current close | Current close |
| **Stop-Loss** | FVG bot × 0.997 | FVG top × 1.003 |
| **TP1** | entry + (entry - SL) × 1.5 | entry - (SL - entry) × 1.5 |
| **TP2** | entry + (entry - SL) × 2.5 | entry - (SL - entry) × 2.5 |

## Context Filter
- 1H HTF bias must align with FVG direction.
- Bullish FVG in bearish 1H trend → skip.

## Failure Scenario
- FVG is filled (price trades through the full gap) → remove from watchlist.
- Signal expires after 15 candles without entry trigger.
