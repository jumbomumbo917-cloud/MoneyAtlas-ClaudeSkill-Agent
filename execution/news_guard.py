# execution/news_guard.py
#
# High Market Risk (HMR) news-window guard.
#
# Mirrors what Exness does around high-impact news: it caps max leverage
# (e.g. to 1:200) during volatile event windows because spreads widen and
# price gaps can jump straight through a stop. This guard lets the bot:
#   - know whether a timestamp falls inside an HMR window,
#   - clamp the effective leverage to the window's cap, and
#   - optionally block new entries entirely during the window.
#
# HMR windows are scheduled by the broker and published in the app. Feed in
# whatever the Exness Analytics screen shows for the day.

from dataclasses import dataclass
from datetime import datetime, time
from typing import List, Optional


@dataclass
class HMRWindow:
    start: time
    end: time
    max_leverage: int
    event: str = ""

    def contains(self, t: time) -> bool:
        return self.start <= t <= self.end


@dataclass
class GuardDecision:
    in_window: bool
    effective_leverage: int
    blocked: bool
    reason: str = ""
    window: Optional[HMRWindow] = None


# Default HMR windows taken from the Exness Analytics screenshot.
# Times are local to the broker schedule shown in the app.
DEFAULT_HMR_WINDOWS: List[HMRWindow] = [
    HMRWindow(time(10, 45), time(11, 1), 200, "Factory Orders MoM"),
    HMRWindow(time(1, 28), time(3, 10), 1000, "High-impact window"),
    HMRWindow(time(10, 45), time(11, 1), 200, "Balance of Trade / Industrial Production"),
]


class NewsGuard:
    """Clamps leverage (and optionally blocks entries) during HMR windows."""

    def __init__(self, windows: Optional[List[HMRWindow]] = None, block_in_window: bool = False):
        self.windows = windows if windows is not None else DEFAULT_HMR_WINDOWS
        # If True, refuse any new entry during a window. If False, just clamp leverage.
        self.block_in_window = block_in_window

    def active_window(self, when: datetime) -> Optional[HMRWindow]:
        t = when.time()
        active = [w for w in self.windows if w.contains(t)]
        if not active:
            return None
        # If overlapping windows, the most conservative (lowest cap) wins.
        return min(active, key=lambda w: w.max_leverage)

    def evaluate(self, account_leverage: int, when: Optional[datetime] = None) -> GuardDecision:
        when = when or datetime.utcnow()
        window = self.active_window(when)

        if window is None:
            return GuardDecision(in_window=False, effective_leverage=account_leverage, blocked=False)

        if self.block_in_window:
            return GuardDecision(
                in_window=True, effective_leverage=window.max_leverage, blocked=True,
                reason=(f"HMR window {window.start.strftime('%H:%M')}-"
                        f"{window.end.strftime('%H:%M')} ({window.event}): new entries "
                        f"blocked — news gap risk."),
                window=window,
            )

        effective = min(account_leverage, window.max_leverage)
        reason = ""
        if effective < account_leverage:
            reason = (f"HMR window {window.start.strftime('%H:%M')}-"
                      f"{window.end.strftime('%H:%M')} ({window.event}): leverage clamped "
                      f"1:{account_leverage} -> 1:{effective}.")
        return GuardDecision(in_window=True, effective_leverage=effective, blocked=False,
                             reason=reason, window=window)
