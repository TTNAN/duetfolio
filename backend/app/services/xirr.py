"""XIRR (annualized internal rate of return) in pure Python.

Cash-flow convention: negative = money out of pocket (buys), positive =
money back (sells, dividends, terminal portfolio value).
"""
from datetime import date


def xnpv(rate: float, cashflows: list[tuple[date, float]]) -> float:
    if rate <= -1:
        return float("inf")
    t0 = cashflows[0][0]
    return sum(cf / (1 + rate) ** ((d - t0).days / 365.0) for d, cf in cashflows)


def xirr(
    cashflows: list[tuple[date, float]],
    guess: float = 0.1,
    tol: float = 1e-7,
    max_iter: int = 100,
) -> float | None:
    """Return annualized IRR, or None when undefined (e.g. all flows one-signed)."""
    flows = sorted(cashflows, key=lambda x: x[0])
    if len(flows) < 2:
        return None
    amounts = [cf for _, cf in flows]
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        return None

    # Newton-Raphson with numerical derivative
    r = guess
    for _ in range(max_iter):
        f = xnpv(r, flows)
        if abs(f) < tol:
            return r
        h = 1e-6
        df = (xnpv(r + h, flows) - f) / h
        if abs(df) < 1e-12:
            break
        r_new = r - f / df
        if r_new <= -1:
            break
        if abs(r_new - r) < tol:
            return r_new
        r = r_new

    # Bisection fallback on a wide bracket
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = xnpv(lo, flows), xnpv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = xnpv(mid, flows)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2
