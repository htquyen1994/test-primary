"""
Live Market Analysis
=====================
Fetch OHLCV from Binance and apply system scoring logic.
Run: python market_analysis.py
"""

import sys
import io
from pathlib import Path
# Fix Windows console encoding for Unicode symbols
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
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
    """
    1H bias — mirrors detect_htf_bias() in engine/smc.py.
    Uses swing structure (higher highs/lows), NOT EMA20/50.
    EMA200 as primary trend filter, swing for confirmation.

    FIX 2026-05-16: Previous version used EMA20/EMA50 which does NOT match
    the system's actual context filter (engine/context.py uses detect_htf_bias).
    """
    if len(df) < 50: return "neutral"
    # Primary: EMA200 position (same as system's detect_htf_bias)
    e200_series = ema(df['close'], 200)
    if e200_series.isna().all(): return "neutral"
    e200 = e200_series.iloc[-1]
    p = df['close'].iloc[-1]

    # Swing structure check (last SWING_LOOKBACK candles)
    lookback = min(15, len(df) - 1)
    recent = df.iloc[-lookback - 1:-1]
    lows  = recent['low'].values
    highs = recent['high'].values
    higher_lows  = sum(1 for i in range(1, len(lows))  if lows[i]  > lows[i-1])
    lower_highs  = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i-1])
    n_pairs = len(lows) - 1

    if p > e200 and higher_lows >= 0.6 * n_pairs: return "bullish"
    if p < e200 and lower_highs >= 0.6 * n_pairs: return "bearish"
    if p > e200: return "bullish"   # price above EMA200 as fallback
    if p < e200: return "bearish"
    return "neutral"


def mtf_scenario(b4h, b1h, direction):
    """
    MTF Scenario A/B/C — mirrors get_mtf_alignment() in engine/mtf_bias.py.
    Scenario C: 4H directly opposing signal direction (ADX > 20 implied by detect_4h_bias).
    FIX 2026-05-16: Removed erroneous explicit ADX > 25 check — the ADX filter
    is already embedded inside detect_4h_bias()/bias_4h() which returns "bearish"
    only when ADX > ADX_TRENDING_THRESHOLD (20).
    """
    signal_bias   = "bullish" if direction == "long" else "bearish"
    opposite_bias = "bearish" if signal_bias == "bullish" else "bullish"
    if b4h == opposite_bias: return "C", 0.0, "BLOCK"  # 4H opposing → BLOCK
    if b4h == signal_bias:   return "A", 1.0, +10      # 4H aligned
    return "B", 0.5, -10                                # 4H ranging

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

    # OB feed status — check Redis (non-blocking, fallback to unknown)
    ob_available = False
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trading-core"))
        from pathlib import Path as _Path
        _env = _Path(__file__).parent.parent.parent / "backend-workspace" / ".env"
        if _env.exists():
            for _line in _env.read_text().splitlines():
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _, _v = _line.partition('=')
                    _os.environ.setdefault(_k.strip(), _v.strip())
        import redis as _redis_lib, json as _json, time as _time
        _r = _redis_lib.Redis(host='localhost', port=6379, decode_responses=True)
        _binance_sym = symbol.replace('/', '')  # BTC/USDT → BTCUSDT
        _snap = _r.get(f'ob:{symbol}:snap')    # try ccxt-style key first
        if not _snap:
            _snap = _r.get(f'ob:{_binance_sym}:snap')
        if _snap:
            _ob = _json.loads(_snap)
            _age = _time.time() - _ob.get('updated_at', 0)
            ob_available = _age <= 60 and (_ob.get('bid_stack', 0) > 0)
    except Exception:
        ob_available = False  # Redis not accessible in this context

    # Max score estimate (realistic, not theoretical max)
    # SMC realistic best: CHoCH+OB+FVG = 30, but usually 10-20
    # VSA realistic best: NoSupply+EvR = 20, sometimes +POC = 30
    # Context: 1H aligned=8, funding=4, S/R=3 → max 15; realistic with bias aligned = 11
    ctx_pts = 11 if direction in ("long", "short") else 4  # 8 bias + funding 3 (S/R uncertain)
    of_pts  = 25 if ob_available else 0   # bid+absorption possible; delta may be partial
    raw_best = of_pts + 30 + 20 + ctx_pts + 15  # SMC=30, VSA=20 (optimistic)
    final_best = min(round(raw_best * mult / 125 * 100), 100)

    # Apply MTF score adjustment
    if direction != "neutral":
        sc, _, sa = mtf_scenario(b4, b1, direction)
        if sc == "A": final_best = min(100, final_best + 10)
        elif sc == "B": final_best = max(0, final_best - 10)
        elif sc == "C": final_best = 0

    # Apply data quality cap
    if not ob_available:
        final_best = min(final_best, 60)

    ob_status = f"{'OK' if ob_available else 'MISS'}"
    print(f"\n  OB Feed: {ob_status} | Max score: {final_best}/100 | ALERT threshold: 75")
    if final_best >= 75:
        print(f"  => ALERT POSSIBLE — conditions: SMC CHoCH + OB retest + FVG touch needed")
    elif final_best >= 55:
        print(f"  => WATCH possible, ALERT needs: {'OB data' if not ob_available else 'better SMC/VSA conditions'}")
    else:
        print(f"  => IGNORE range — {'start OB feed' if not ob_available else 'market conditions unfavorable'}")

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
