# Strategy Spec: Engulfing

## Glossary
- **Engulfing**: Two-candle pattern where the second candle's body fully contains the first candle's body.
- **Bullish Engulfing**: Bearish candle followed by a larger bullish candle.
- **Bearish Engulfing**: Bullish candle followed by a larger bearish candle.

## Mathematical Logic
```
Bullish Engulfing:
  candle[T] is bullish:   close[T] > open[T]
  candle[T-1] is bearish: close[T-1] < open[T-1]
  candle[T].open  <= candle[T-1].close  (opens at or below prior close)
  candle[T].close >= candle[T-1].open   (closes at or above prior open)

Bearish Engulfing: mirror conditions
  candle[T] is bearish, candle[T-1] is bullish
  candle[T].open  >= candle[T-1].close
  candle[T].close <= candle[T-1].open
```

## Objective Entry/Exit
| | Long | Short |
|---|---|---|
| **Trigger** | Bullish engulfing candle closes | Bearish engulfing candle closes |
| **Entry** | Close of engulfing candle | Close of engulfing candle |
| **Stop-Loss** | candle[T-1].low × 0.998 | candle[T-1].high × 1.002 |
| **TP1** | entry + (entry - SL) × 1.5 | entry - (SL - entry) × 1.5 |
| **TP2** | entry + (entry - SL) × 2.5 | entry - (SL - entry) × 2.5 |

## Context Filter
- 1H HTF bias must align: bullish engulfing requires bullish 1H bias.

## Failure Scenario
- Price closes beyond the engulfed candle's wick → invalidated.
- Signal expires after 15 candles.
