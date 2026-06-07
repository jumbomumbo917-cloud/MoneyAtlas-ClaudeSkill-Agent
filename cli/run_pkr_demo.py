# cli/run_pkr_demo.py
#
# DEMO: trading a PKR 5,000 account on gold (XAUUSD), anchored on the real
# spot price from the user's screenshot ($4,331, Jun 07 2026).
#
# The point of this demo is to show, honestly, what a ~$18 account can and
# cannot do — and how lot sizing has to adapt (Exness Cent account + tight
# scalp stop) for the trade to even be placeable.
#
# Runs fully offline. No broker, no credentials.

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.paper_account import PaperAccount

PKR_PER_USD = 280.0          # approximate; FX rate moves
PKR_BALANCE = 5000.0
GOLD_SPOT = 4331.0           # real spot from the screenshot

# Gold contract sizes (units = ounces per 1.00 lot)
STANDARD_OZ = 100            # standard/micro account: 1 lot = 100 oz
CENT_OZ = 1                  # Exness Cent account: 1 lot = 1 oz (1/100 of standard)
MIN_LOT = 0.01               # broker minimum order size


def generate_gold_path(anchor, n=40, seed=7):
    """Short intraday gold path around the real spot — small $-range candles."""
    random.seed(seed)
    price = anchor
    candles = []
    for _ in range(n):
        o = price
        # gentle downward intraday drift (matches the -0.28% day on the screenshot)
        c = o - 1.2 + random.uniform(-6, 6)
        hi = max(o, c) + random.uniform(0, 3)
        lo = min(o, c) - random.uniform(0, 3)
        candles.append((o, hi, lo, c))
        price = c
    return candles


def usd(pkr):
    return pkr / PKR_PER_USD


def main():
    bal_usd = usd(PKR_BALANCE)
    print(f"Account: PKR {PKR_BALANCE:,.0f}  ≈  ${bal_usd:,.2f} USD  (@ {PKR_PER_USD} PKR/USD)")
    print(f"Gold spot (real, from screenshot): ${GOLD_SPOT:,.2f}\n")

    # --- Reality check: can a standard/micro account even take the trade? ---
    risk_pct = 0.01
    risk_usd = bal_usd * risk_pct
    swing_stop = 40.0   # a normal swing stop on gold is ~$40
    ideal_std = risk_usd / (swing_stop * STANDARD_OZ)
    print("--- Sizing reality check (standard account, $40 swing stop) ---")
    print(f"  Risk budget (1%): ${risk_usd:.2f}")
    print(f"  Ideal lot = {ideal_std:.5f}  → broker min is {MIN_LOT}")
    print(f"  VERDICT: {ideal_std:.5f} << {MIN_LOT} — UN-tradeable. One min-lot would")
    print(f"           risk ${swing_stop*STANDARD_OZ*MIN_LOT:.2f} = "
          f"{swing_stop*STANDARD_OZ*MIN_LOT/bal_usd*100:.0f}% of the account. Blow-up risk.\n")

    # --- The brain part: Cent account + tight scalp stop makes it work ---
    scalp_stop = 5.0    # tight intraday scalp stop
    print("--- Adapted plan: Exness CENT account + $5 scalp stop ---")
    acct = PaperAccount(balance=bal_usd, leverage=500, risk_per_trade=risk_pct, spread=0.30)
    entry = GOLD_SPOT
    sl = entry - scalp_stop          # long scalp
    tp = entry + scalp_stop * 2      # 2R target

    lots = acct.position_size(entry, sl, CENT_OZ)
    print(f"  Entry {entry:.2f} | SL {sl:.2f} (-${scalp_stop}) | TP {tp:.2f} (+${scalp_stop*2}) | 2R")
    print(f"  Sized lot (cent, 1 lot = 1 oz): {lots}  → above min {MIN_LOT}: "
          f"{'YES' if lots >= MIN_LOT else 'NO'}")

    pos = acct.open("XAUUSDc", "long", entry, sl, tp, CENT_OZ)
    if not pos:
        print("  Order rejected.")
        return
    print(f"  FILLED: long {pos.lots} lot @ {pos.entry}\n")

    # --- Walk the price path to resolve the scalp ---
    for o, hi, lo, c in generate_gold_path(GOLD_SPOT):
        acct.mark_to_market("XAUUSDc", hi)
        acct.mark_to_market("XAUUSDc", lo)
        if not acct.positions:
            break
    if acct.positions:
        acct.close_all("XAUUSDc", GOLD_SPOT)

    t = acct.history[-1]
    pnl_pkr = t.pnl * PKR_PER_USD
    print("--- RESULT ---")
    print(f"  {t.direction} {t.lots} @ {t.entry} -> {t.exit} ({t.reason})")
    print(f"  P&L: ${t.pnl:+.2f}  ≈  PKR {pnl_pkr:+,.0f}")
    print(f"  Ending balance: ${acct.balance:.2f}  ≈  PKR {acct.balance*PKR_PER_USD:,.0f}")
    print(f"\n  Report: {acct.report()}")


if __name__ == "__main__":
    main()
