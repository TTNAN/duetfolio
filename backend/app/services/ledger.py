"""Position engine shared by the summary and the history replay.

One function, `apply_txn`, advances a per-instrument position by one
transaction. Two cost-basis methods:

- "wac"  weighted average cost (default; what most HK/CN broker apps show)
- "fifo" first-in-first-out lots (what US brokers / IRS 1099-B default to)

Corporate actions:
- "split": quantity holds the ratio (new shares per old share), e.g. 4 for
  a 1-for-4 split, 0.1 for a 10-to-1 consolidation. Share count scales,
  total cost basis is unchanged, no cash moves.
- "dividend": cash income = quantity * price - fee (fee = withholding tax).
"""
from __future__ import annotations

from dataclasses import dataclass, field

COST_METHODS = ("wac", "fifo")
EPS = 1e-9


@dataclass
class Position:
    qty: float = 0.0
    cost: float = 0.0                 # cost basis of the shares still held
    realized: float = 0.0             # cumulative realized P&L (incl. dividends)
    lots: list = field(default_factory=list)  # FIFO: [[qty, unit_cost], ...]

    def reset(self) -> None:
        self.qty, self.cost, self.lots = 0.0, 0.0, []


def apply_txn(pos: Position, t, method: str = "wac") -> float | None:
    """Advance `pos` by transaction `t`. Returns the realized amount this
    transaction produced (sell P&L or dividend), else None."""
    typ = t.type
    if typ == "buy":
        gross = t.quantity * t.price + t.fee
        pos.qty += t.quantity
        pos.cost += gross
        if t.quantity > 0:
            pos.lots.append([t.quantity, gross / t.quantity])
        return None

    if typ == "sell":
        if pos.qty <= EPS:
            pos.qty -= t.quantity
            if pos.qty <= EPS:
                pos.reset()
            return None
        sq = min(t.quantity, pos.qty)
        if method == "fifo":
            removed, left = 0.0, sq
            while left > EPS and pos.lots:
                lot = pos.lots[0]
                take = min(lot[0], left)
                removed += take * lot[1]
                lot[0] -= take
                left -= take
                if lot[0] <= EPS:
                    pos.lots.pop(0)
        else:
            removed = sq * pos.cost / pos.qty
            # keep lots consistent so switching method later stays sane
            ratio = (pos.qty - sq) / pos.qty
            for lot in pos.lots:
                lot[0] *= ratio
        # sell fee reduces proceeds, never the remaining cost basis
        r = sq * t.price - removed - t.fee
        pos.realized += r
        pos.cost -= removed
        pos.qty -= t.quantity
        if pos.qty <= EPS:
            pos.reset()
        return r

    if typ == "split":
        ratio = t.quantity
        if ratio > 0 and pos.qty > 0:
            pos.qty *= ratio
            for lot in pos.lots:
                lot[0] *= ratio
                lot[1] /= ratio
        return None

    if typ == "dividend":
        r = t.quantity * t.price - t.fee
        pos.realized += r
        return r
    return None


def cash_effect(t) -> float:
    """Cash moved in the brokerage account by `t`, instrument currency."""
    gross = t.quantity * t.price
    if t.type == "buy":
        return -(gross + t.fee)
    if t.type in ("sell", "dividend"):
        return gross - t.fee
    return 0.0  # split: no cash


def split_factor_after(splits: list, d) -> float:
    """Product of split ratios strictly after date `d`.

    Daily history from Yahoo/EastMoney is split-adjusted, so a pre-split
    share count must be scaled by later splits to value it correctly.
    """
    f = 1.0
    for sd, ratio in splits:
        if sd > d and ratio > 0:
            f *= ratio
    return f
