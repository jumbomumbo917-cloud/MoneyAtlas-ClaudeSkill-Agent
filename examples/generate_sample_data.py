# examples/generate_sample_data.py
#
# Generates examples/sample_data.csv: synthetic BTCUSDT 4H OHLCV candles
# that walk through a full Smart Money Cycle (accumulation -> expansion
# -> decision zone -> distribution -> exit liquidity) so the SMC Layer
# Engine has a structurally meaningful dataset to analyze.
#
# Deterministic (fixed seed) so the sample is reproducible.

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

# Each phase: (number of candles, drift per candle, volatility, volume range)
PHASES = [
    (40, 30,    120,  (3000, 5000)),   # accumulation: tight range, high participation
    (30, 380,   260,  (4000, 7000)),   # expansion: strong breakout, rising volume
    (25, 0,     520,  (3500, 6500)),   # decision zone: choppy, wide ranges both ways
    (30, -10,   140,  (3500, 6000)),   # distribution: tight range near highs, fading momentum
    (20, -430,  300,  (5000, 9000)),   # exit liquidity: sharp reversal down on volume spike
]

START_PRICE = 40000.0
START_TIME = datetime(2025, 1, 1)
TIMEFRAME_HOURS = 4

rows = []
price = START_PRICE
timestamp = START_TIME

for count, drift, volatility, volume_range in PHASES:
    for _ in range(count):
        open_price = price
        close_price = open_price + drift + random.uniform(-volatility, volatility)
        high_price = max(open_price, close_price) + random.uniform(0, volatility * 0.6)
        low_price = min(open_price, close_price) - random.uniform(0, volatility * 0.6)
        volume = random.uniform(*volume_range)

        rows.append([
            timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            round(open_price, 2),
            round(high_price, 2),
            round(low_price, 2),
            round(close_price, 2),
            round(volume, 2),
        ])

        price = close_price
        timestamp += timedelta(hours=TIMEFRAME_HOURS)

with open("examples/sample_data.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
    writer.writerows(rows)

print(f"Wrote {len(rows)} candles to examples/sample_data.csv")
