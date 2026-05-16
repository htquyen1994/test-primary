"""
SMC Debug Script
=================
Diagnose why SMC score is low. Runs each function step-by-step.
Run: python debug_smc.py [symbol]  (default: BTC/USDT)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend-workspace"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trading-core"))

import ccxt
import pandas as pd
import numpy as np

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT"

exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

def fetch(symbol, tf, limit=200):
    raw = exchange.fetch_ohlcv(symbol, tf, limit=limit)
    df = pd.DataFrame(raw, columns=['ts','open','high','low','close','volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    return df.set_index('ts')

print(f"Fetching {SYMBOL} data...")
df_15m = fetch(SYMBOL, '15m', 200)
df_1h  = fetch(SYMBOL, '1h',  100)

from engine.smc import (
    find_order_block, find_fvg, detect_choch, detect_htf_bias,
    compute_smc_score, OB_ATR_MULTIPLIER, SWING_LOOKBACK,
    FVG_TOUCH_TOLERANCE, OB_RETEST_TOLERANCE, _compute_fib_levels
)
from indicators.atr import ATR

price = float(df_15m['close'].iloc[-1])
atr_val = float(ATR().compute(df_15m, 14).dropna().iloc[-1])

print(f"\n{'='*65}")
print(f"  {SYMBOL} | Price: ${price:,.4f} | ATR(14): ${atr_val:,.4f} ({atr_val/price*100:.3f}%)")
print(f"  OB_ATR_MULT={OB_ATR_MULTIPLIER} | SWING_LOOKBACK={SWING_LOOKBACK} | FVG_TOL={FVG_TOUCH_TOLERANCE*100:.2f}%")
print(f"{'='*65}")

# ── CHoCH ─────────────────────────────────────────────────────────────────────
print(f"\n--- CHoCH (SWING_LOOKBACK={SWING_LOOKBACK}) ---")
ref = df_15m.iloc[-SWING_LOOKBACK:-1]
sh = float(ref['high'].max())
sl = float(ref['low'].min())
lc = float(df_15m['close'].iloc[-1])
print(f"  Swing high: ${sh:,.4f} | Swing low: ${sl:,.4f} | Last close: ${lc:,.4f}")
print(f"  Bullish threshold: ${sh*(1+0.0005):,.4f} | Gap: {(sh*(1+0.0005)-lc)/lc*100:+.3f}%")
print(f"  Bearish threshold: ${sl*(1-0.0005):,.4f} | Gap: {(lc-sl*(1-0.0005))/lc*100:+.3f}%")
choch = detect_choch(df_15m)
print(f"  Result: {choch if choch else 'None — price inside swing range'}")

# ── HTF Bias ──────────────────────────────────────────────────────────────────
print(f"\n--- HTF Bias (1H) ---")
htf = detect_htf_bias(df_1h)
print(f"  Result: '{htf}'")

# ── Order Blocks ──────────────────────────────────────────────────────────────
print(f"\n--- Order Blocks (OB_ATR_MULT={OB_ATR_MULTIPLIER}) ---")
bodies = [abs(float(df_15m.iloc[i+1]['close']) - float(df_15m.iloc[i+1]['open']))
          for i in range(len(df_15m)-2, max(0, len(df_15m)-52), -1)]
qualifying = [b for b in bodies if b >= atr_val * OB_ATR_MULTIPLIER]
print(f"  Min impulse body: ${atr_val*OB_ATR_MULTIPLIER:,.4f}")
print(f"  Qualifying candles: {len(qualifying)}/{len(bodies)} (median body: ${sorted(bodies)[len(bodies)//2]:,.4f})")
obs = find_order_block(df_15m, OB_ATR_MULTIPLIER)
print(f"  OBs found: {len(obs)}")
for i, ob in enumerate(obs):
    dist = abs(price - ob.mid) / price * 100
    retesting = ob.is_price_retesting(price)
    print(f"  OB[{i}]: {ob.type.upper()} ${ob.low:,.4f}-${ob.high:,.4f} | dist={dist:.2f}% | retesting={retesting}")

# ── FVG ───────────────────────────────────────────────────────────────────────
print(f"\n--- FVG (tolerance={FVG_TOUCH_TOLERANCE*100:.2f}%) ---")
fvg = find_fvg(df_15m)
if fvg:
    dist = abs(price - fvg.mid) / price * 100
    tol_price = fvg.mid * FVG_TOUCH_TOLERANCE
    touching = fvg.is_price_at_midpoint(price)
    print(f"  FVG: {fvg.type.upper()} ${fvg.bot:,.4f}-${fvg.top:,.4f} | mid=${fvg.mid:,.4f}")
    print(f"  Distance: {dist:.3f}% | Tolerance: {FVG_TOUCH_TOLERANCE*100:.2f}% | Touching: {touching}")
    if not touching:
        print(f"  => Need price in ${fvg.mid-tol_price:,.4f}-${fvg.mid+tol_price:,.4f}")
else:
    print("  No unfilled FVG found")

# ── Full Score ────────────────────────────────────────────────────────────────
print(f"\n--- Full SMC Score ---")
for direction in ["long", "short"]:
    r = compute_smc_score(df_15m, df_1h, signal_direction=direction, htf_bias=htf)
    print(f"  {direction.upper()}: {r.score}/30 | CHoCH={r.choch_aligned} OB={r.ob_retested} FVG={r.fvg_touched}")

# ── Diagnosis ─────────────────────────────────────────────────────────────────
print(f"\n--- DIAGNOSIS ---")
issues = []
if not choch:
    issues.append(f"CHoCH: price inside swing range, need breakout")
if not obs:
    issues.append(f"OB: no qualifying impulse candles (try OB_ATR_MULTIPLIER < {OB_ATR_MULTIPLIER})")
elif not any(ob.is_price_retesting(price) for ob in obs):
    issues.append(f"OB: found {len(obs)} OBs but price not retesting (wait for pullback)")
if fvg and not fvg.is_price_at_midpoint(price):
    dist = abs(price - fvg.mid) / price * 100
    issues.append(f"FVG: midpoint {dist:.3f}% away, tolerance {FVG_TOUCH_TOLERANCE*100:.2f}% (try increasing)")

if issues:
    for i, issue in enumerate(issues, 1):
        print(f"  [{i}] {issue}")
else:
    print("  No issues — SMC should be scoring")
