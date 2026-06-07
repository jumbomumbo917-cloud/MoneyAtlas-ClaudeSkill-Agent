# execution/position_sizer.py
#
# Compliance-aware position sizer.
#
# Given an account (balance, leverage, risk%) and a trade (entry, stop,
# contract size), it computes the lot that:
#   1. risks no more than risk% of the balance (risk-first sizing),
#   2. is snapped to the broker's lot step and >= the minimum lot,
#   3. fits within available margin for the chosen leverage,
#   4. stays under any max-lot cap.
#
# It NEVER silently rounds risk up. If the risk-correct lot is below the
# broker minimum, it does not force a min-lot trade — it reports the trade as
# non-compliant and tells you exactly why, because forcing min-lot on a tiny
# account is the classic blow-up. The human decides what to do with that.

from dataclasses import dataclass, field
from typing import List


@dataclass
class SizingResult:
    tradeable: bool
    lots: float                 # compliant lot to use (0.0 if not tradeable)
    ideal_lots: float           # risk-perfect lot before broker constraints
    risk_amount: float          # currency risked at the compliant lot
    risk_pct_actual: float      # that risk as a % of balance
    margin_required: float      # margin locked for the compliant lot
    free_margin_after: float    # balance - margin
    warnings: List[str] = field(default_factory=list)
    reason: str = ""            # why not tradeable (if applicable)


def _snap_to_step(value: float, step: float) -> float:
    """Round DOWN to the nearest lot step so risk never rounds up."""
    if step <= 0:
        return value
    steps = int(value / step + 1e-9)
    return round(steps * step, 10)


def size_position(
    balance: float,
    leverage: int,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    contract_size: float,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    max_lot: float = 100.0,
) -> SizingResult:
    """Pick the largest broker-compliant lot that respects the risk budget."""
    warnings: List[str] = []
    stop_distance = abs(entry - stop_loss)

    if stop_distance == 0:
        return SizingResult(False, 0.0, 0.0, 0.0, 0.0, 0.0, balance,
                            reason="Stop-loss equals entry — undefined risk.")

    risk_budget = balance * risk_pct
    ideal_lots = risk_budget / (stop_distance * contract_size)

    # 1) Snap down to a valid lot step
    lots = _snap_to_step(ideal_lots, lot_step)

    # 2) Below broker minimum? Not compliant — do NOT force min-lot.
    if lots < min_lot:
        min_lot_risk = stop_distance * contract_size * min_lot
        return SizingResult(
            tradeable=False, lots=0.0, ideal_lots=round(ideal_lots, 5),
            risk_amount=0.0, risk_pct_actual=0.0, margin_required=0.0,
            free_margin_after=balance,
            warnings=warnings,
            reason=(f"Risk-correct lot {ideal_lots:.5f} is below broker minimum "
                    f"{min_lot}. Trading one min-lot would risk "
                    f"{min_lot_risk:,.2f} = {min_lot_risk / balance * 100:.0f}% of "
                    f"the account. Reduce stop distance, use a Cent account, or skip."),
        )

    # 3) Cap at max lot
    if lots > max_lot:
        lots = max_lot
        warnings.append(f"Capped at max lot {max_lot}.")

    # 4) Margin check against leverage
    notional = lots * contract_size * entry
    margin_required = notional / leverage if leverage else notional

    if margin_required > balance:
        # Shrink the lot to what margin allows, then re-snap down
        affordable = (balance * leverage) / (contract_size * entry)
        lots = _snap_to_step(affordable, lot_step)
        if lots < min_lot:
            return SizingResult(
                tradeable=False, lots=0.0, ideal_lots=round(ideal_lots, 5),
                risk_amount=0.0, risk_pct_actual=0.0, margin_required=0.0,
                free_margin_after=balance, warnings=warnings,
                reason=(f"Even one min-lot needs more margin than the balance at "
                        f"1:{leverage}. Raise leverage or balance."),
            )
        notional = lots * contract_size * entry
        margin_required = notional / leverage
        warnings.append(f"Lot reduced to {lots} to fit available margin at 1:{leverage}.")

    risk_amount = stop_distance * contract_size * lots
    return SizingResult(
        tradeable=True,
        lots=round(lots, 5),
        ideal_lots=round(ideal_lots, 5),
        risk_amount=round(risk_amount, 2),
        risk_pct_actual=round(risk_amount / balance * 100, 2),
        margin_required=round(margin_required, 2),
        free_margin_after=round(balance - margin_required, 2),
        warnings=warnings,
    )
