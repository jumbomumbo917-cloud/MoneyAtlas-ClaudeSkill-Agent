# cli/run_btc_demo.py
#
# DEMO: BTC/USD hourly trading on a PKR-denominated Exness account.
#
# Account is in PKR, so balance / margin / risk / P&L are all PKR.
# BTC price levels (entry / SL / TP) stay in their USD quote, because
# BTC/USD is always *priced* in dollars regardless of account currency.
#
# Real values from the Exness screen (8 Jun 2026):
#   bid 63,125.10 | ask 63,135.18 | spread $10.08 | 4H downtrend
#   support 59,073 | resistance 66,700
#
# PKR-native trick: PaperAccount computes P&L = move * lots * contract_size.
# For BTC, 1 lot = 1 BTC and a $1 move = $1; to express that in PKR we set
# contract_size = 1 BTC * PKR_PER_USD, so every result comes out in PKR.
#
# Fully offline. No broker, no credentials.

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.paper_account import PaperAccount

PKR_PER_USD = 280.0          # FX rate moves; verify current rate

PKR_BALANCE = 10000.0        # account is in PKR

# Real market values (BTC price quoted in USD)
BID = 63125.10
ASK = 63135.18
SPREAD = ASK - BID           # $10.08 in quote points
SUPPORT = 59073.29
RESISTANCE = 66700.64

LEVERAGE = 500
RISK_PCT = 0.10              # up to 10% per trade

# 1 BTC lot priced into PKR: 1 BTC * PKR/USD -> account math is all PKR
PKR_CONTRACT = 1 * PKR_PER_USD


def gen_path(start, drift, n=30, vol=120, seed=1):
    """Synthetic hourly BTC path (USD quote): drift = direction, vol = candle range."""
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


def run_scenario(label, direction, entry, stop, target, path):
    acct = PaperAccount(balance=PKR_BALANCE, leverage=LEVERAGE,
                        risk_per_trade=RISK_PCT, spread=SPREAD)
    sizing = acct.size(entry, stop, PKR_CONTRACT)
    stop_dist = abs(entry - stop)

    print(f"\n=== {label} ===")
    print(f"  {direction.upper()}")
    print(f"  Entry (BTC/USD quote): {entry:,.2f}")
    print(f"  Stop-loss            : {stop:,.2f}   (${stop_dist:,.0f} away)")
    print(f"  Take-profit          : {target:,.2f}   ({abs(target-entry)/stop_dist:.1f}R)")
    print(f"  Lot size (auto)      : {sizing.lots} lot")
    print(f"  Risk                 : PKR {sizing.risk_amount:,.0f} ({sizing.risk_pct_actual}%)")
    print(f"  Margin locked        : PKR {sizing.margin_required:,.0f}")
    print(f"  Spread cost on entry : PKR {SPREAD * sizing.lots * PKR_CONTRACT:,.0f}")

    pos = acct.open("BTCUSD", direction, entry, stop, target, PKR_CONTRACT)
    if not pos:
        print(f"  REJECTED: {sizing.reason or 'spread tipped risk over the limit'}")
        return

    for o, hi, lo, c in path:
        acct.mark_to_market("BTCUSD", hi)
        acct.mark_to_market("BTCUSD", lo)
        if not acct.positions:
            break
    if acct.positions:
        acct.close_all("BTCUSD", path[-1][3])

    t = acct.history[-1]
    print(f"  --> {t.reason.upper()} at {t.exit:,.2f}")
    print(f"  --> P&L: PKR {t.pnl:+,.0f}")
    print(f"  --> Balance: PKR {PKR_BALANCE:,.0f} -> PKR {acct.balance:,.0f}")


def main():
    print(f"BTC/USD demo | Account PKR {PKR_BALANCE:,.0f} | 1:{LEVERAGE} | "
          f"risk {RISK_PCT*100:.0f}% | spread ${SPREAD:.2f} | rate {PKR_PER_USD} PKR/USD")
    print(f"Real levels (USD quote): support {SUPPORT:,.0f} | "
          f"spot {ASK:,.0f} | resistance {RESISTANCE:,.0f}")

    run_scenario(
        "A) Counter-trend LONG scalp (off the bounce)", "long",
        entry=ASK, stop=ASK - 300, target=ASK + 600,
        path=gen_path(ASK, drift=45, vol=110, seed=3),
    )

    run_scenario(
        "B) With-trend SHORT (failed retest of resistance)", "short",
        entry=RESISTANCE, stop=RESISTANCE + 300, target=RESISTANCE - 600,
        path=gen_path(RESISTANCE, drift=-55, vol=110, seed=7),
    )

    print("\nNote: prices are BTC/USD quotes; everything account-side is PKR.")
    print("1:500 only lowers the margin locked — risk is set by stop + lot.")


if __name__ == "__main__":
    main()
