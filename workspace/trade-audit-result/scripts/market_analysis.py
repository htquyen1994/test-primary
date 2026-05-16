"""
Live Market Analysis
=====================
Fetch OHLCV from Binance and apply system scoring logic.
Run: python market_analysis.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend-workspace"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trading-core"))

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# ── Indicators ────────────────────────────────────────────────────────────────

def atr(df, p=14):
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False).mean()

def adx(df, p=14):
    h, l, c = df['high'], df['low'], df['close']
    ph, pl, pc = h.shift(1), l.shift(1), c.shift(1)
    pdm = (h - ph).clip(lower=0)
    mdm = (pl - l).clip(lower=0)
    pdm = pdm.where(pdm > mdm, 0)
    mdm = mdm.where(mdm > pdm, 0)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1/p, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1/p, adjust=False).mean() / atr14
    mdi = 100 * mdm.ewm(alpha=1/p, adjust=False).mean() / atr14
    dx = (100 * (pdi - mdi).abs() / (pdi + mdi)).fillna(0)
    return dx.ewm(alpha=1/p, adjust=False).mean()

def rsi(df, p=14):
    d = df['close'].diff()
    g = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
    ls = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
    return 100 - (100 / (1 + g / ls.replace(0, np.nan)))

def ema(s, p): return s.ewm(span=p, adjust=False).mean()

def bb(df, p=20, k=2):
    m = df['close'].rolling(p).mean()
    s = df['close'].rolling(p).std()
    return m + k*s, m, m - k*s

# ── Regime ────────────────────────────────────────────────────────────────────

def regime(df_1h, df_15m):
    adx_1h = adx(df_1h).iloc[-1]
    atr_15m = atr(df_15m)
    cur = atr_15m.iloc[-1]
    avg = atr_15m.rolling(20).mean().iloc[-1]
    if cur > 3.0 * avg:   return "PARABOLIC", 0.6, adx_1h, cur, avg
    elif adx_1h > 25:     return "TRENDING",  1.0, adx_1h, cur, avg
    elif adx_1h < 20:     return "CHOPPY",    0.85, adx_1h, cur, avg
    else:                 return "RANGING",   0.85, adx_1h, cur, avg

# ── MTF Bias ──────────────────────────────────────────────────────────────────

def bias_4h(df):
    if len(df) < 200: return "ranging"
    e200 = ema(df['close'], 200).iloc[-1]
    price = df['close'].iloc[-1]
    adx_v = adx(df).iloc[-1]
    lows = df['low'].iloc[-10:].values
    highs = df['high'].iloc[-10:].values
    hl = all(lows[i] >= lows[i-1] for i in range(1, len(lows)))
    lh = all(highs[i] <= highs[i-1] for i in range(1, len(highs)))
    if price > e200 and hl and adx_v > 20: return "bullish"
    if price < e200 and lh and adx_v > 20: return "bearish"
    return "ranging"

def bias_daily(df):
    if len(df) < 200: return "NEUTRAL"
    e200 = ema(df['close'], 200).iloc[-1]
    e50  = ema(df['close'], 50).iloc[-1]
    price = df['close'].iloc[-1]
    lows10 = df['low'].iloc[-10:].values
    highs10 = df['high'].iloc[-10:].values
    hl_cnt = sum(1 for i in range(1, len(lows10)) if lows10[i] > lows10[i-1])
    lh_cnt = sum(1 for i in range(1, len(highs10)) if highs10[i] < highs10[i-1])
    if price > e200 and price > e50 and hl_cnt >= 3: return "BULL"
    if price < e200 and price < e50 and lh_cnt >= 3: return "BEAR"
    return "NEUTRAL"

def bias_1h(df):
    if len(df) < 50: return "neutral"
    e20 = ema(df['close'], 20).iloc[-1]
    e50 = ema(df['close'], 50).iloc[-1]
    p = df['close'].iloc[-1]
    if p > e20 > e50: return "bullish"
    if p < e20 < e50: return "bearish"
    return "neutral"

def mtf_scenario(b4h, b1h, direction):
    aligned = (direction == "long" and b4h == "bullish" and b1h == "bullish") or \
              (direction == "short" and b4h == "bearish" and b1h == "bearish")
    opposing = (direction == "long" and b4h == "bearish") or \
               (direction == "short" and b4h == "bullish")
    if aligned:  return "A", 1.0, +10
    if opposing: return "C", 0.0, "BLOCK"
    return "B", 0.5, -10

# ── Main ──────────────────────────────────────────────────────────────────────

def analyze(exchange, symbol):
    print(f"\n{'='*68}")
    print(f"  {symbol}")
    print(f"{'='*68}")

    def fetch(tf, limit):
        raw = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df = pd.DataFrame(raw, columns=['ts','open','high','low','close','volume'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
        return df.set_index('ts')

    df_15m = fetch('15m', 200)
    df_1h  = fetch('1h',  200)
    df_4h  = fetch('4h',  250)
    df_1d  = fetch('1d',  300)

    price = df_15m['close'].iloc[-1]
    print(f"  Price: ${price:,.4f} | {df_15m.index[-1].strftime('%Y-%m-%d %H:%M UTC')}")

    reg, mult, adx_v, atr_cur, atr_avg = regime(df_1h, df_15m)
    print(f"\n  REGIME: {reg} (×{mult}) | ADX(1H)={adx_v:.1f} | ATR ratio={atr_cur/atr_avg:.2f}x")

    bd = bias_daily(df_1d)
    b4 = bias_4h(df_4h)
    b1 = bias_1h(df_1h)
    print(f"  MTF BIAS: Daily={bd} | 4H={b4} | 1H={b1}")

    direction = "long" if b1 == "bullish" else ("short" if b1 == "bearish" else "neutral")
    if direction != "neutral":
        sc, sm, sa = mtf_scenario(b4, b1, direction)
        print(f"  {direction.upper()} → Scenario {sc} | size ×{sm} | score adj: {sa}")

    rsi_v = rsi(df_15m).iloc[-1]
    adx_15 = adx(df_15m).iloc[-1]
    e200 = ema(df_1h['close'], 200).iloc[-1]
    bbu, bbm, bbl = bb(df_15m)
    bb_pct = (price - bbl.iloc[-1]) / (bbu.iloc[-1] - bbl.iloc[-1]) * 100 if bbu.iloc[-1] != bbl.iloc[-1] else 50
    print(f"\n  RSI(15m)={rsi_v:.1f} | ADX(15m)={adx_15:.1f} | EMA200(1H)=${e200:,.0f}")
    print(f"  BB position: {bb_pct:.0f}% (0=lower, 100=upper)")
    print(f"  Price {'ABOVE' if price > e200 else 'BELOW'} EMA200 1H")

    # Max score estimate
    ctx_pts = 12 if (direction == "long" and b1 == "bullish") or (direction == "short" and b1 == "bearish") else 4
    raw_best = 0 + 30 + 20 + ctx_pts + 15  # OF=0, SMC=30, VSA=20
    final_best = min(round(raw_best * mult / 125 * 100), 100)
    final_best = min(final_best, 60)  # data quality cap
    print(f"\n  Max achievable score (no OB feed): {final_best}/100 | ALERT threshold: 75")
    if final_best >= 75:
        print(f"  => ALERT POSSIBLE if SMC/VSA conditions met")
    else:
        print(f"  => Need Order Book feed to reach ALERT")

    return {"symbol": symbol, "price": price, "regime": reg, "daily": bd, "4h": b4, "1h": b1,
            "rsi": rsi_v, "adx": adx_15, "max_score": final_best, "direction": direction}


def main():
    print(f"\n{'#'*68}")
    print(f"  LIVE MARKET ANALYSIS — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'#'*68}")

    ex = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    results = []
    for s in symbols:
        try:
            results.append(analyze(ex, s))
        except Exception as e:
            print(f"  ERROR {s}: {e}")

    print(f"\n\n{'#'*68}")
    print(f"  SUMMARY")
    print(f"{'#'*68}")
    print(f"  {'Symbol':<12} {'Price':>12} {'Regime':<12} {'Daily':<8} {'4H':<10} {'1H':<10} {'RSI':>6} {'MaxScore':>9}")
    print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*8} {'-'*10} {'-'*10} {'-'*6} {'-'*9}")
    for r in results:
        print(f"  {r['symbol']:<12} ${r['price']:>11,.2f} {r['regime']:<12} {r['daily']:<8} {r['4h']:<10} {r['1h']:<10} {r['rsi']:>6.1f} {r['max_score']:>8}/100")

if __name__ == "__main__":
    main()
