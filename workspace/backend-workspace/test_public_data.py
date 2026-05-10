import ccxt
exchange = ccxt.binance({"enableRateLimit": True})

ob = exchange.fetch_order_book("BTC/USDT", limit=5)
print("Order Book (public, no API key):")
print(f"  Best bid: {ob['bids'][0][0]} x {ob['bids'][0][1]} BTC")
print(f"  Best ask: {ob['asks'][0][0]} x {ob['asks'][0][1]} BTC")
bid_stack = sum(b[1] for b in ob["bids"][:5])
ask_stack = sum(a[1] for a in ob["asks"][:5])
print(f"  Bid stack (top 5): {bid_stack:.2f} BTC")
print(f"  Ask stack (top 5): {ask_stack:.2f} BTC")
print(f"  Bid dominant: {bid_stack > ask_stack * 2}")

trades = exchange.fetch_trades("BTC/USDT", limit=5)
print("\nRecent trades (public, no API key):")
delta = 0
for t in trades:
    delta += t["amount"] if t["side"] == "buy" else -t["amount"]
    print(f"  {t['side']:4s} {t['amount']:.4f} BTC @ {t['price']}")
print(f"  Delta (5 trades): {delta:+.4f} BTC")
print("\nBoth Order Book and Trade Tape are PUBLIC - no API key needed!")
