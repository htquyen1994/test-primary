# Strategy Spec: Order Block (OB)

## Glossary
- **Order Block (OB)**: The last opposing candle before a strong directional impulse move.
- **Impulse**: A candle whose body >= 1.5 × ATR(14).
- **Bullish OB**: A bearish candle immediately before a bullish impulse.
- **Bearish OB**: A bullish candle immediately before a bearish impulse.
- **Retest**: Price returns to the OB zone after the impulse.
- **ATR**: Average True Range (14-period Wilder smoothing).

## Mathematical Logic
```
impulse_body = abs(candle[i+1].close - candle[i+1].open)
is_impulse   = impulse_body >= 1.5 * ATR(14)

Bullish OB: candle[i+1] is bullish AND candle[i] is bearish AND is_impulse
Bearish OB: candle[i+1] is bearish AND candle[i] is bullish AND is_impulse

OB zone: [ob.low, ob.high]
OB mid:  (ob.high + ob.low) / 2

Retest: ob.low - tolerance <= current_price <= ob.high + tolerance
        where tolerance = ob.mid * 0.002 (0.2%)

Invalidation: Bullish OB → close < ob.low; Bearish OB → close > ob.high
```

## Objective Entry/Exit
| | Long | Short |
|---|---|---|
| **Trigger** | Close of retest candle within bullish OB zone | Close of retest candle within bearish OB zone |
| **Entry** | Current close price | Current close price |
| **Stop-Loss** | ob.low × 0.997 | ob.high × 1.003 |
| **TP1** | entry + (entry - SL) × 1.5 | entry - (SL - entry) × 1.5 |
| **TP2** | entry + (entry - SL) × 2.5 | entry - (SL - entry) × 2.5 |

## Context Filter
- 1H HTF bias must align: bullish OB requires bullish 1H bias (HH+HL structure)
- Bearish OB requires bearish 1H bias (LH+LL structure)
- Neutral 1H bias → skip signal

## Failure Scenario
- OB is invalidated when price closes beyond the OB zone (below ob.low for bullish, above ob.high for bearish)
- Signal expires after 15 candles (225 minutes on 15m timeframe) without entry trigger
- HTF bias reversal after 5 candles → immediate cancellation
