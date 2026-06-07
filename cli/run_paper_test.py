# cli/run_paper_test.py
#
# End-to-end PAPER-TRADING test of the Money Atlas strategy.
# Runs entirely offline: no broker, no credentials, no network.
#
#   1. Load OHLCV candles
#   2. SMC Layer Engine maps the institutional cycle
#   3. SignalEngine derives a trade from the layer structure
#   4. PaperAccount sizes it by risk and simulates the fill
#   5. Walk the remaining candles to see if it hits TP or SL
#   6. Print the result
#
# Usage:  python3 cli/run_paper_test.py

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smc.smc_layer_masterpiece import SMCLayerEngine, load_ohlcv_csv
from execution.signal_engine import SignalEngine
from execution.paper_account import PaperAccount

# XAUUSD-style contract: 1.00 lot = 100 oz, so $1 move = $100 per lot.
CONTRACT_SIZE = 100
SYMBOL = "BTCUSDT"          # sample data is BTC; swap in your own CSV + symbol
SPLIT = 0.7                 # use first 70% of candles to decide, walk the rest


async def main():
    candles = load_ohlcv_csv("examples/sample_data.csv")
    split_idx = int(len(candles) * SPLIT)
    history, future = candles[:split_idx], candles[split_idx:]

    # 1-2. Analyze structure on the history window
    engine = SMCLayerEngine()
    layer_map = await engine.analyze(symbol=SYMBOL, timeframe="4H", candles=history)

    print("=== SMC STRUCTURE ===")
    print(f"Current layer: L{layer_map.current_layer} @ {layer_map.current_price}")
    for l in layer_map.layers:
        print(f"  L{l.layer} {l.phase:<14} {l.price_low:>10.2f}-{l.price_high:<10.2f} "
              f"state={l.state:<13} conf={l.confidence}")

    # 3. Derive signal
    signal = SignalEngine().generate_signal(layer_map)
    if not signal:
        print("\nNo trade signal from current structure. Nothing to test.")
        return
    print(f"\n=== SIGNAL ===\n{signal}")

    # 4. Open the paper position (1:500 leverage, 1% risk, BTC contract = 1 unit)
    account = PaperAccount(balance=10_000, leverage=500, risk_per_trade=0.01, spread=2.0)
    pos = account.open(
        symbol=signal.symbol, direction=signal.direction,
        entry=signal.entry, stop_loss=signal.stop_loss,
        take_profit=signal.take_profit, contract_size=1,  # BTC: 1 lot = 1 coin
    )
    if not pos:
        print("\nPosition rejected (size <= 0 or exceeds leverage).")
        return
    print(f"\n=== PAPER ORDER FILLED ===\n{pos}")

    # 5. Walk forward candle-by-candle to resolve the trade
    for c in future:
        account.mark_to_market(signal.symbol, c.high)
        account.mark_to_market(signal.symbol, c.low)
        if not account.positions:
            break
    if account.positions:
        account.close_all(signal.symbol, future[-1].close)  # close at end if unresolved

    # 6. Report
    print("\n=== RESULT ===")
    for t in account.history:
        print(f"  {t.direction} {t.lots} @ {t.entry} -> {t.exit} "
              f"({t.reason}) pnl={t.pnl:+.2f}")
    print(f"\n{account.report()}")


if __name__ == "__main__":
    asyncio.run(main())
