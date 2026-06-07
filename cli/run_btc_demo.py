# cli/run_btc_demo.py
#
# DEMO: BTC/USD hourly trading on a PKR 10,000 account, using the REAL levels
# from the Exness screen (8 Jun 2026):
#   bid 63,125.10 | ask 63,135.18 | spread $10.08 | 4H downtrend
#   recent low 59,073 (support) | overhead resistance 66,700
#
# Simulates BOTH plays the analysis described, auto-sized at 10% risk / 1:500:
#   A) counter-trend LONG scalp off the bounce
#   B) with-trend SHORT on a failed retest of resistance
#
# Fully offline. No broker, no credentials.

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.paper_account import PaperAccount

PKR_PER_USD = 280.0
PKR_BALANCE = 10000.0

# Real market values from the screenshot
BID = 63125.10
ASK = 63135.18
SPREAD = ASK - BID            # $10.08
SUPPORT = 59073.29
RESISTANCE = 66700.64

LEVERAGE = 500
RISK_PCT = 0.10              # user accepts up to 10% per trade
BTC_CONTRACT = 1            # Exness BTCUSD: 1 lot = 1 BTC


def gen_path(start, drift, n=30, vol=120, seed=1):
    """Synthetic hourly BTC path: drift sets direction, vol sets candle range."""
    random.seed(seed)
    price = start
    out = []
    for _ in range(n):
        o = price
        c = o + drift + random.uniform(-vol, vol)
        hi = max(o, c) + random.uniform(0, vol)
        lo = min(o, c) - random.uniform(0, vol)
        out.append((o, hi, lo, c))
        price = c
    return out


def run_scenario(label, direction, entry, stop, target, path, seed):
    acct = PaperAccount(balance=PKR_BALANCE / PKR_PER_USD, leverage=LEVERAGE,
                        risk_per_trade=RISK_PCT, spread=SPREAD)
    sizing = acct.size(entry, stop, BTC_CONTRACT)
    stop_dist = abs(entry - stop)

    print(f"\n=== {label} ===")
    print(f"  {direction.upper()} entry {entry:,.0f} | SL {stop:,.0f} (${stop_dist:,.0f}) | "
          f"TP {target:,.0f} | {abs(target-entry)/stop_dist:.1f}R")
    print(f"  Auto-sized: {sizing.lots} lot | risk PKR {sizing.risk_amount*PKR_PER_USD:,.0f} "
          f"({sizing.risk_pct_actual}%) | margin PKR {sizing.margin_required*PKR_PER_USD:,.0f}")
    spread_cost = SPREAD * sizing.lots * BTC_CONTRACT
    print(f"  Spread cost on entry: PKR {spread_cost*PKR_PER_USD:,.0f}")

    pos = acct.open("BTCUSD", direction, entry, stop, target, BTC_CONTRACT)
    if not pos:
        print(f"  REJECTED: {sizing.reason}")
        return

    for o, hi, lo, c in path:
        acct.mark_to_market("BTCUSD", hi)
        acct.mark_to_market("BTCUSD", lo)
        if not acct.positions:
            break
    if acct.positions:
        acct.close_all("BTCUSD", path[-1][3])

    t = acct.history[-1]
    print(f"  RESULT: {t.direction} {t.lots} @ {t.entry:,.0f} -> {t.exit:,.0f} ({t.reason}) "
          f"| P&L ${t.pnl:+.2f} = PKR {t.pnl*PKR_PER_USD:+,.0f}")
    print(f"  Ending balance: PKR {acct.balance*PKR_PER_USD:,.0f}")


def main():
    bal = PKR_BALANCE / PKR_PER_USD
    print(f"BTC/USD demo | PKR {PKR_BALANCE:,.0f} (${bal:.2f}) | 1:{LEVERAGE} | "
          f"risk {RISK_PCT*100:.0f}% | spread ${SPREAD:.2f}")
    print(f"Real levels: support {SUPPORT:,.0f} | spot {ASK:,.0f} | resistance {RESISTANCE:,.0f}")

    # A) Counter-trend long scalp off the bounce ($300 stop ~8.4%, leaves room for spread)
    run_scenario(
        "A) Counter-trend LONG scalp", "long",
        entry=ASK, stop=ASK - 300, target=ASK + 600,
        path=gen_path(ASK, drift=45, vol=110, seed=3), seed=3,
    )

    # B) With-trend short on a failed retest of resistance
    run_scenario(
        "B) With-trend SHORT (failed retest of resistance)", "short",
        entry=RESISTANCE, stop=RESISTANCE + 300, target=RESISTANCE - 600,
        path=gen_path(RESISTANCE, drift=-55, vol=110, seed=7), seed=7,
    )

    print("\nNote: leverage 1:500 only lowered the margin locked; the risk (PKR ~1,000")
    print("at 10%) is identical to any other leverage. Stop + size set the risk.")


if __name__ == "__main__":
    main()
