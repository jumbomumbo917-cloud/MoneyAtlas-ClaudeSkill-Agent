# cli/run_csv_analysis.py
#
# Run the SMC Layer Engine on a real CoinMarketCap historical CSV.
#
# CMC exports differ from the engine's native format:
#   - semicolon-delimited, UTF-8 BOM
#   - newest-first ordering
#   - extra columns (marketCap, supply, etc.)
#   - sometimes duplicated rows
# This loader normalizes all of that, then runs real structural analysis.
#
# Usage:  python3 cli/run_csv_analysis.py <path-to-cmc.csv> [symbol] [timeframe]

import asyncio
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smc.smc_layer_masterpiece import SMCLayerEngine, Candle
from execution.signal_engine import SignalEngine


def load_cmc_csv(path):
    """Load a CoinMarketCap CSV -> de-duplicated, oldest-first list of Candle."""
    seen = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ts = (r.get("timeOpen") or "").strip()
            if not ts:
                continue
            # de-dupe on the day key; last write wins (rows are identical anyway)
            seen[ts[:10]] = Candle(
                timestamp=ts,
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r.get("volume") or 0.0),
            )
    return [seen[k] for k in sorted(seen)]


async def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "examples/sample_data.csv"
    symbol = sys.argv[2] if len(sys.argv) > 2 else "BTCUSD"
    timeframe = sys.argv[3] if len(sys.argv) > 3 else "1D"

    candles = load_cmc_csv(path)
    print(f"Loaded {len(candles)} candles | {candles[0].timestamp[:10]} -> {candles[-1].timestamp[:10]}")
    lo = min(c.low for c in candles); hi = max(c.high for c in candles)
    print(f"Price range: ${lo:,.0f} -> ${hi:,.0f} | latest close ${candles[-1].close:,.0f}\n")

    result = await SMCLayerEngine().analyze(symbol=symbol, timeframe=timeframe, candles=candles)

    print(f"=== SMC STRUCTURE ({symbol} {timeframe}) ===")
    print(f"Current price ${result.current_price:,.0f} sits in LAYER L{result.current_layer}\n")
    for l in result.layers:
        marker = "  <-- HERE" if l.layer == result.current_layer else ""
        print(f"  L{l.layer} {l.phase:<14} ${l.price_low:>9,.0f} - ${l.price_high:<9,.0f}  "
              f"state={l.state:<13} conf={l.confidence} (n={l.candle_count}){marker}")

    print("\n=== SIGNAL ===")
    sig = SignalEngine().generate_signal(result)
    print(sig if sig else "No long-accumulation signal from current structure.")


if __name__ == "__main__":
    asyncio.run(main())
