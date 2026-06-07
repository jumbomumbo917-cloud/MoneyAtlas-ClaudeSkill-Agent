# cli/run_sizing.py
#
# Auto-sizing tool: for a given balance / risk% / trade, show the compliant
# lot the bot would use across every Exness leverage option — so you can see
# exactly which leverage actually lets the trade through and at what risk.
#
# Usage:  python3 cli/run_sizing.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.position_sizer import size_position

# ----- Edit these for your scenario -----
PKR_PER_USD = 280.0
PKR_BALANCE = 5000.0
RISK_PCT = 0.01
ENTRY = 4331.0          # real gold spot
STOP = 4326.0           # $5 scalp stop
CONTRACT_SIZE = 1       # Exness Cent gold: 1 lot = 1 oz
# Exness leverage menu from the screenshot
LEVERAGES = [2000, 1000, 800, 600, 500, 400, 200, 100, 50, 20, 2]


def main():
    balance = PKR_BALANCE / PKR_PER_USD
    print(f"Balance: PKR {PKR_BALANCE:,.0f} ≈ ${balance:.2f} | risk {RISK_PCT*100:.0f}% "
          f"| entry {ENTRY} stop {STOP} (${abs(ENTRY-STOP):.0f}) | Cent gold 1 lot = {CONTRACT_SIZE} oz\n")
    print(f"{'Leverage':<10}{'Lot':<10}{'Risk $':<10}{'Risk %':<9}{'Margin $':<10}Verdict")
    print("-" * 70)

    for lev in LEVERAGES:
        r = size_position(
            balance=balance, leverage=lev, risk_pct=RISK_PCT,
            entry=ENTRY, stop_loss=STOP, contract_size=CONTRACT_SIZE,
        )
        if r.tradeable:
            verdict = "OK" + (f"  [{'; '.join(r.warnings)}]" if r.warnings else "")
            print(f"1:{lev:<8}{r.lots:<10}{r.risk_amount:<10}{r.risk_pct_actual:<9}"
                  f"{r.margin_required:<10}{verdict}")
        else:
            print(f"1:{lev:<8}{'-':<10}{'-':<10}{'-':<9}{'-':<10}BLOCKED — {r.reason[:60]}...")

    print("\nRule: leverage sets how much margin is locked, NOT your risk.")
    print("Risk is fixed by stop-loss + lot. Pick the lowest leverage that still")
    print("lets the compliant lot through — here that's where 'OK' first appears.")


if __name__ == "__main__":
    main()
