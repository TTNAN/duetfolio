"""XIRR (annualized internal rate of return) in pure Python.

Cash-flow convention: negative = money out of pocket (buys), positive =
money back (sells, dividends, terminal portfolio value).

Solver strategy (robust for frequent, alternating deposits/withdrawals):
1. Newton-Raphson with an analytic derivative — fast when it converges.
2. If Newton stalls (derivative ~0, oscillation, divergence, rate <= -100%),
   scan a log-spaced grid of rates for sign changes of XNPV and solve each
   bracket with Brent's method, which is guaranteed to converge.
3. With several roots (possible when flows change sign more than once),
   return the one closest to the guess — the economically sensible one.
"""
from datetime import date
import math


def _years(cashflows: list[tuple[date, float]]) -> list[float]:
    t0 = cashflows[0][0]
    return [(d - t0).days / 365.0 for d, _ in cashflows]


def xnpv(rate: float, cashflows: list[tuple[date, float]]) -> float:
    if rate <= -1:
        return float("inf")
    t0 = cashflows[0][0]
    try:
        return sum(cf / (1 + rate) ** ((d - t0).days / 365.0) for d, cf in cashflows)
    except OverflowError:
        return float("inf")


def _xnpv_and_deriv(rate: float, amounts: list[float], years: list[float]) -> tuple[float, float]:
    base = 1.0 + rate
    f = df = 0.0
    for a, t in zip(amounts, years):
        disc = base ** -t
        f += a * disc
        df += -t * a * disc / base
    return f, df


def _brent(fn, a: float, b: float, fa: float, fb: float,
           tol: float = 1e-10, max_iter: int = 200) -> float | None:
    """Brent's root finder on a bracket where fa and fb have opposite signs."""
    if fa * fb > 0:
        return None
    if abs(fa) < abs(fb):
        a, b, fa, fb = b, a, fb, fa
    c, fc, d = a, fa, b - a
    mflag = True
    for _ in range(max_iter):
        if fb == 0 or abs(b - a) < tol:
            return b
        if fa != fc and fb != fc:  # inverse quadratic interpolation
            s = (a * fb * fc / ((fa - fb) * (fa - fc))
                 + b * fa * fc / ((fb - fa) * (fb - fc))
                 + c * fa * fb / ((fc - fa) * (fc - fb)))
        else:  # secant
            s = b - fb * (b - a) / (fb - fa)
        cond = (
            not ((3 * a + b) / 4 < s < b or b < s < (3 * a + b) / 4)
            or (mflag and abs(s - b) >= abs(b - c) / 2)
            or (not mflag and abs(s - b) >= abs(c - d) / 2)
            or (mflag and abs(b - c) < tol)
            or (not mflag and abs(c - d) < tol)
        )
        if cond:  # fall back to bisection
            s = (a + b) / 2
            mflag = True
        else:
            mflag = False
        fs = fn(s)
        d, c, fc = c, b, fb
        if fa * fs < 0:
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b, fa, fb = b, a, fb, fa
    return b


def _grid() -> list[float]:
    """Candidate rates from -99.99% to +1000%, dense near zero."""
    pts = {-0.9999, -0.99, -0.95, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3,
           -0.2, -0.15, -0.1, -0.05, -0.02, 0.0, 0.02, 0.05, 0.1, 0.15, 0.2,
           0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0}
    return sorted(pts)


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
    years = _years(flows)

    # 1) Newton-Raphson
    r = guess
    for _ in range(max_iter):
        try:
            f, df = _xnpv_and_deriv(r, amounts, years)
        except (OverflowError, ZeroDivisionError):
            break
        if not math.isfinite(f) or not math.isfinite(df):
            break
        if abs(f) < tol:
            return r
        if abs(df) < 1e-12:
            break
        r_new = r - f / df
        if r_new <= -1 or not math.isfinite(r_new) or abs(r_new) > 1e3:
            break
        if abs(r_new - r) < tol:
            return r_new
        r = r_new

    # 2) bracket scan + Brent
    fn = lambda x: xnpv(x, flows)
    grid = _grid()
    vals = [fn(x) for x in grid]
    roots = []
    for (a, fa), (b, fb) in zip(zip(grid, vals), zip(grid[1:], vals[1:])):
        if not (math.isfinite(fa) and math.isfinite(fb)):
            continue
        if fa == 0:
            roots.append(a)
        elif fa * fb < 0:
            root = _brent(fn, a, b, fa, fb)
            if root is not None:
                roots.append(root)
    if vals and math.isfinite(vals[-1]) and vals[-1] == 0:
        roots.append(grid[-1])
    if not roots:
        return None
    return min(roots, key=lambda x: abs(x - guess))
