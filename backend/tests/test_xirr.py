"""XIRR unit tests — cases hand-verified in the 2026-10-02 code review."""
from datetime import date

from app.services.xirr import xirr


def test_one_year_10pct():
    r = xirr([(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1100.0)])
    assert r is not None and abs(r - 0.10) < 1e-4


def test_four_days_small_gain_annualizes():
    # +0.1% over 4 days -> ~9.5% annualized (extreme but mathematically right)
    r = xirr([(date(2026, 1, 1), -1000.0), (date(2026, 1, 5), 1001.0)])
    assert r is not None and abs(r - 0.0955) < 1e-3


def test_all_positive_returns_none():
    assert xirr([(date(2026, 1, 1), 100.0), (date(2026, 2, 1), 200.0)]) is None


def test_single_cashflow_returns_none():
    assert xirr([(date(2026, 1, 1), -100.0)]) is None


def test_loss_is_negative():
    r = xirr([(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 900.0)])
    assert r is not None and abs(r - (-0.10)) < 1e-4


# ---- robustness: cases where plain Newton-Raphson stalls or diverges ----
from app.services.xirr import xnpv


def test_near_total_loss_converges():
    # -99.9%: Newton from 10% overshoots below -100% -> bracket fallback
    r = xirr([(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 1.0)])
    assert r is not None and abs(r - (-0.999)) < 1e-4


def test_huge_gain_converges():
    # 10x in a year = +900%
    r = xirr([(date(2025, 1, 1), -1000.0), (date(2026, 1, 1), 10000.0)])
    assert r is not None and abs(r - 9.0) < 1e-3


def test_frequent_alternating_large_flows():
    # monthly big deposits and withdrawals of alternating sign
    flows = []
    for m in range(1, 13):
        amt = -50000.0 if m % 2 else 42000.0
        flows.append((date(2025, m, 1), amt))
    flows.append((date(2026, 1, 1), 60000.0))
    r = xirr(flows)
    assert r is not None
    assert abs(xnpv(r, flows)) < 1e-3 * 50000


def test_tiny_horizon_extreme_rate():
    # +5% in 2 days annualizes to a huge number; must not crash or hang
    r = xirr([(date(2026, 1, 1), -1000.0), (date(2026, 1, 3), 1050.0)])
    assert r is None or r > 5.0
