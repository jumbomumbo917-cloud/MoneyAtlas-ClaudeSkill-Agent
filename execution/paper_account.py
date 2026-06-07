# execution/paper_account.py
#
# Paper-trading account simulator.
#
# Runs fully self-contained (no broker, no network, no credentials) so the
# Money Atlas strategy can be tested end-to-end. Models the things that
# actually matter for an Exness-style CFD/forex account: balance, equity,
# leverage, spread, contract size, and risk-based position sizing.

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PaperPosition:
    symbol: str
    direction: str          # "long" / "short"
    lots: float
    entry: float
    stop_loss: float
    take_profit: float
    contract_size: float    # units per 1.00 lot (e.g. 100 oz for XAUUSD)
    opened_at: str


@dataclass
class ClosedTrade:
    symbol: str
    direction: str
    lots: float
    entry: float
    exit: float
    pnl: float
    reason: str             # "tp" / "sl" / "manual"
    opened_at: str
    closed_at: str


@dataclass
class PaperAccount:
    """Simulated trading account with Exness-style mechanics."""

    balance: float
    leverage: int = 500                 # Exness offers high leverage; default 1:500
    risk_per_trade: float = 0.01        # 1% of equity risked per position
    spread: float = 0.30                # price units added on entry (e.g. gold ~$0.30)
    positions: List[PaperPosition] = field(default_factory=list)
    history: List[ClosedTrade] = field(default_factory=list)

    @property
    def equity(self) -> float:
        return self.balance

    def position_size(self, entry: float, stop_loss: float, contract_size: float) -> float:
        """Risk-based lot sizing: risk_amount / (stop_distance * contract_size)."""
        risk_amount = self.balance * self.risk_per_trade
        stop_distance = abs(entry - stop_loss)
        if stop_distance == 0:
            return 0.0
        lots = risk_amount / (stop_distance * contract_size)
        return round(lots, 2)

    def open(self, symbol, direction, entry, stop_loss, take_profit, contract_size) -> Optional[PaperPosition]:
        # apply spread against the trader on entry
        fill = entry + self.spread if direction == "long" else entry - self.spread
        lots = self.position_size(fill, stop_loss, contract_size)
        if lots <= 0:
            return None

        # reject if notional exceeds available leverage
        notional = lots * contract_size * fill
        if notional > self.balance * self.leverage:
            return None

        pos = PaperPosition(
            symbol=symbol, direction=direction, lots=lots, entry=round(fill, 2),
            stop_loss=stop_loss, take_profit=take_profit,
            contract_size=contract_size, opened_at=datetime.utcnow().isoformat(),
        )
        self.positions.append(pos)
        return pos

    def _pnl(self, pos: PaperPosition, exit_price: float) -> float:
        move = exit_price - pos.entry if pos.direction == "long" else pos.entry - exit_price
        return round(move * pos.lots * pos.contract_size, 2)

    def mark_to_market(self, symbol: str, price: float):
        """Check open positions against current price; close any that hit SL/TP."""
        still_open = []
        for pos in self.positions:
            if pos.symbol != symbol:
                still_open.append(pos)
                continue

            hit = None
            if pos.direction == "long":
                if price <= pos.stop_loss:
                    hit = ("sl", pos.stop_loss)
                elif price >= pos.take_profit:
                    hit = ("tp", pos.take_profit)
            else:  # short
                if price >= pos.stop_loss:
                    hit = ("sl", pos.stop_loss)
                elif price <= pos.take_profit:
                    hit = ("tp", pos.take_profit)

            if hit:
                reason, exit_price = hit
                self._close(pos, exit_price, reason)
            else:
                still_open.append(pos)

        self.positions = still_open

    def _close(self, pos: PaperPosition, exit_price: float, reason: str):
        pnl = self._pnl(pos, exit_price)
        self.balance = round(self.balance + pnl, 2)
        self.history.append(ClosedTrade(
            symbol=pos.symbol, direction=pos.direction, lots=pos.lots,
            entry=pos.entry, exit=exit_price, pnl=pnl, reason=reason,
            opened_at=pos.opened_at, closed_at=datetime.utcnow().isoformat(),
        ))

    def close_all(self, symbol: str, price: float):
        for pos in [p for p in self.positions if p.symbol == symbol]:
            self._close(pos, price, "manual")
        self.positions = [p for p in self.positions if p.symbol != symbol]

    def report(self) -> dict:
        wins = [t for t in self.history if t.pnl > 0]
        losses = [t for t in self.history if t.pnl <= 0]
        total_pnl = round(sum(t.pnl for t in self.history), 2)
        return {
            "ending_balance": self.balance,
            "net_pnl": total_pnl,
            "trades": len(self.history),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(self.history), 2) if self.history else 0.0,
            "open_positions": len(self.positions),
        }
