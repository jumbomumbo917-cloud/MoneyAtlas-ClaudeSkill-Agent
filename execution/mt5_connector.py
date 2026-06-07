# execution/mt5_connector.py
#
# Exness (MetaTrader 5) connector — RUN THIS ON YOUR OWN MACHINE.
#
# IMPORTANT
# ---------
# This module CANNOT run in the Claude Code cloud sandbox. The `MetaTrader5`
# package only works on Windows with the MT5 terminal installed and running
# locally; it talks to the terminal over local IPC, not the internet. You run
# this on your own PC, against your Exness account.
#
# SAFETY: defaults to a DEMO account and refuses to place live orders unless
# you explicitly pass allow_live=True. Test on demo first. Always.
#
# Setup (on your Windows machine):
#   1. Install the Exness MT5 terminal and log into your DEMO account.
#   2. pip install MetaTrader5
#   3. Put your demo credentials in environment variables (never hard-code):
#         set MT5_LOGIN=<your demo login number>
#         set MT5_PASSWORD=<your demo password>
#         set MT5_SERVER=<e.g. Exness-MT5Trial>
#   4. python -m execution.mt5_connector   (runs the self-check below)

import os

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # absent in the sandbox / on non-Windows machines


class MT5Connector:
    """Thin wrapper over the MetaTrader5 terminal API for Exness demo trading."""

    def __init__(self, login=None, password=None, server=None, allow_live=False):
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 package not available. Install it and run on a "
                "Windows machine with the Exness MT5 terminal."
            )
        self.login = int(login or os.environ["MT5_LOGIN"])
        self.password = password or os.environ["MT5_PASSWORD"]
        self.server = server or os.environ["MT5_SERVER"]
        self.allow_live = allow_live

    def connect(self):
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            raise ConnectionError(f"MT5 initialize failed: {mt5.last_error()}")

        info = mt5.account_info()
        if info is None:
            raise ConnectionError("Could not read account info after connect.")

        # Hard guard: refuse to operate on a real-money account unless opted in.
        is_demo = info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
        if not is_demo and not self.allow_live:
            mt5.shutdown()
            raise PermissionError(
                "Connected account is NOT a demo account and allow_live=False. "
                "Aborting to protect real funds."
            )
        return {"login": info.login, "balance": info.balance,
                "currency": info.currency, "demo": is_demo}

    def place_order(self, symbol, direction, lots, sl, tp):
        """Send a market order. Blocked on live accounts unless allow_live=True."""
        info = mt5.account_info()
        if info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO and not self.allow_live:
            raise PermissionError("Refusing live order: allow_live=False.")

        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if direction == "long" else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == "long" else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 20260607,
            "comment": "MoneyAtlas",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return {
            "retcode": result.retcode,
            "ok": result.retcode == mt5.TRADE_RETCODE_DONE,
            "order": result.order,
            "price": result.price,
            "comment": result.comment,
        }

    def disconnect(self):
        mt5.shutdown()


if __name__ == "__main__":
    # Self-check: connect to the demo account and print balance. No orders.
    conn = MT5Connector()
    print("Connecting to MT5...")
    print(conn.connect())
    print("Connected. (No orders placed — this is a connection self-check.)")
    conn.disconnect()
