# Exness Testing — How It Works & What You Need To Do

There are two testing paths. Read this before wiring anything to a broker.

## Why I can't trade Exness from the cloud session

- Exness has **no public trading REST API** — all execution is via MetaTrader 4/5.
- The `MetaTrader5` Python package runs **only on Windows**, talking to a locally
  installed MT5 terminal over local IPC. There is no API key to hand to a remote agent.
- The Claude Code cloud sandbox is headless Linux and network-restricted, so it can
  neither run the terminal nor reach Exness servers.

So "giving access" to trade Exness from the cloud is not possible. Instead:

---

## Path 1 — Paper trading (runs anywhere, no account needed)

Fully offline simulation of the Money Atlas strategy.

```bash
python3 cli/run_paper_test.py
```

It maps SMC structure → generates a signal → sizes the position at your risk %
→ walks candles forward to resolve TP/SL → prints P&L and win rate.
Edit `cli/run_paper_test.py` to change capital, risk %, spread, leverage, or to
point at your own OHLCV CSV.

---

## Path 2 — Exness DEMO via MT5 (runs on YOUR Windows machine)

This is the real "execute trades" path, on a demo account, under your control.

### What you need to do
1. Install the **Exness MT5 terminal** and log into a **demo** account.
2. `pip install MetaTrader5`
3. Set credentials as environment variables (never hard-code them):
   ```cmd
   set MT5_LOGIN=<your demo login>
   set MT5_PASSWORD=<your demo password>
   set MT5_SERVER=<e.g. Exness-MT5Trial>
   ```
4. Connection self-check (places **no** orders):
   ```bash
   python -m execution.mt5_connector
   ```
5. Once connected, wire `MT5Connector.place_order(...)` to the signal from
   `SignalEngine` (same signal the paper test uses).

### Safety guards built in
- Defaults to **demo only**. `connect()` and `place_order()` **refuse** to act on a
  real-money account unless you explicitly pass `allow_live=True`.
- Always validate a strategy on Path 1 and a demo account before considering live.

> Even with live trading enabled, the system gives scenario frameworks, not
> guarantees. The human places and owns every live decision.
