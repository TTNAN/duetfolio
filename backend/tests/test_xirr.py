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
