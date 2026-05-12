# Strategy Spec: Pinbar

## Glossary
- **Pinbar**: A candle whose tail is at least 2× the length of its body.
- **Tail**: The wick extending beyond the body in the rejection direction.
- **Body**: abs(close - open).
- **Body Position**: Where the body sits within the total range [0=bottom, 1=top].

## Mathematical Logic
```
body_length  = abs(close - open)
lower_wick   = min(open, close) - low
upper_wick   = high - max(open, close)
candle_range = high - low
body_position = (min(open, close) - low) / candle_range

Long Pinbar:
  lower_wick >= 2 × body_length
  body_position >= 0.70  (body in upper 70% of range)

Short Pinbar:
  upper_wick >= 2 × body_length
  body_position <= 0.30  (body in lower 30% of range)
```

## Objective Entry/Exit
| | Long | Short |
|---|---|---|
| **Trigger** | Long pinbar at OB zone or FVG midpoint | Short pinbar at OB zone or FVG midpoint |
| **Entry** | Close of pinbar candle | Close of pinbar candle |
| **Stop-Loss** | candle.low × 0.998 | candle.high × 1.002 |
| **TP1** | entry + (entry - SL) × 1.5 | entry - (SL - entry) × 1.5 |
| **TP2** | entry + (entry - SL) × 2.5 | entry - (SL - entry) × 2.5 |

## Context Filter
- Must occur at a key S/R level: valid Order Block zone OR FVG midpoint.
- 1H HTF bias must align with pinbar direction.

## Failure Scenario
- Price closes beyond the tail tip (below low for long, above high for short) → invalidated.
- Signal expires after 15 candles.
