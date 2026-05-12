# Test inject một log entry giả vào logs:channel
.venv\Scripts\python -c "
import redis, json
from datetime import datetime, timezone
r = redis.from_url('redis://localhost:6379/0')
entry = {
    'type': 'scoring_log',
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'symbol': 'BTC/USDT',
    'timeframe': '15m',
    'candle_timestamp': datetime.now(timezone.utc).isoformat(),
    'regime': 'TRENDING',
    'regime_multiplier': 1.0,
    'adx': 28.5,
    'atr': 450.2,
    'scores': {'order_flow': 0, 'smc': 10, 'vsa': 10, 'context': 12, 'bonus': 0, 'raw': 32, 'final': 26},
    'classification': 'IGNORE',
    'conditions_met': ['1H bias = bullish → +8 pts', 'Funding rate 0.01% neutral → +4 pts', 'No Supply detected → +10 pts', 'OB retest → +10 pts'],
    'conditions_missed': ['Delta 450 BTC < threshold 1000 → 0/15 pts', 'No FVG midpoint touch → 0/10 pts', 'No CHoCH aligned → 0/10 pts'],
    'why_not_alert': 'Need 49 more points to reach ALERT threshold (75)',
    'delta': 450,
    'funding_rate': 0.0001,
    'portfolio_heat': 0.0,
    'htf_bias': 'bullish'
}
r.publish('logs:channel', json.dumps(entry))
print('Log published to logs:channel')
"
