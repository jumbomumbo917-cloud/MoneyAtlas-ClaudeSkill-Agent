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

# Real market values (BTC price quoted in USD) — updated from latest screen
BID = 63233.64
ASK = 63243.72
SPREAD = ASK - BID           # $10.08 in quote points
SUPPORT = 59073.29
RESISTANCE = 66644.65

LEVERAGE = 500
RISK_PCT = 0.10              # up to 10% per trade

# Rough BTC hourly range used to ESTIMATE holding time (verify against live ATR)
BTC_HOURLY_RANGE = 350.0     # ~typical $ move per 1h candle in current conditions
ATR_4H = 1314.93             # REAL 4H ATR from the indicator screen

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


def run_scenario(label, direction, entry, stop, target, path, risk_pct=RISK_PCT):
    acct = PaperAccount(balance=PKR_BALANCE, leverage=LEVERAGE,
                        risk_per_trade=risk_pct, spread=SPREAD)
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

    # Holding-time estimate: distance to target / typical hourly range.
    tp_hours = abs(target - entry) / BTC_HOURLY_RANGE
    sl_hours = stop_dist / BTC_HOURLY_RANGE
    time_stop = max(2, round(tp_hours * 2))
    print(f"  Est. time to TP      : ~{tp_hours:.1f}h  (SL could hit in ~{sl_hours:.1f}h)")
    print(f"  Time-stop (exit if flat): {time_stop}h — don't let a stalled scalp tie up risk")

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

    # C) NEW: with-trend SHORT now, ATR-based stop, 30% risk accepted.
    # Stop ~0.76x ATR (outside single-candle noise); target rides toward the low.
    atr_stop = 1000.0   # ~0.76x the $1,315 4H ATR; risk lands ~28% at 0.01 lot
    run_scenario(
        "C) ATR-BASED with-trend SHORT (30% risk, sound stop)", "short",
        entry=BID, stop=BID + atr_stop, target=BID - atr_stop * 2,   # 2R
        path=gen_path(BID, drift=-90, vol=180, seed=11),
        risk_pct=0.30,
    )

    print("\nNote: prices are BTC/USD quotes; everything account-side is PKR.")
    print(f"Scenario C stop = ${atr_stop:,.0f} = {atr_stop/ATR_4H:.2f}x ATR — finally OUTSIDE")
    print("the noise. That is what the 30% risk tolerance buys you on a PKR 10k account.")


if __name__ == "__main__":
    main()
