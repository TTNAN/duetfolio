"""Portfolio engine regression tests.

Each test mirrors a scenario from the 2026-10-02 code review that caught a
real defect (P0-1..P0-4). If any of these fail, the numbers are lying.
"""
from datetime import date

import pytest

from app.services import portfolio as pf
from tests.conftest import add_instrument, add_price, add_txn


def _scenario_p0_1(db):
    inst = add_instrument(db)
    add_txn(db, inst, "buy", 100, 10.0, date=date(2026, 1, 1))
    add_txn(db, inst, "sell", 50, 12.0, date=date(2026, 2, 1))
    add_price(db, inst, 12.0, date=date(2026, 3, 1))
    return inst


def test_p0_1_realized_pnl_not_lost(db):
    _scenario_p0_1(db)
    s = pf.portfolio_summary(db, base="USD")
    assert s.total_invested == 500.0      # remaining cost basis
    assert s.total_value == 600.0
    assert s.realized_pnl == 100.0       # 50*(12-10)
    assert s.unrealized_pnl == 100.0     # 600-500
    assert s.total_pnl == 200.0          # the number the review hand-computed
    assert s.holdings[0].realized_pnl == 100.0


def test_p0_3_no_negative_cost_after_full_sell(db):
    """Buy 100@10 fee 10, sell all 100@12 fee 10 -> qty 0, invested 0 (was -10)."""
    inst = add_instrument(db)
    add_txn(db, inst, "buy", 100, 10.0, fee=10.0, date=date(2026, 1, 1))
    add_txn(db, inst, "sell", 100, 12.0, fee=10.0, date=date(2026, 2, 1))
    h = pf.compute_holdings(db)[0]
    assert h["quantity"] == 0.0
    assert h["invested"] == 0.0
    # realized = 100*12 - (100*10+10 buy cost incl. fee) - 10 sell fee = 180
    assert h["realized_pnl"] == 180.0


def test_p0_4_oversell_rejected(db):
    """Selling more than held must raise 400, never create negative qty."""
    from fastapi import HTTPException
    from app.api.routes import create_transaction
    from app.schemas.schemas import TransactionCreate
    from app.services import market as mk
    mk.fetch_fx_to_hkd_on = lambda *a: 7.85  # no network in tests
    inst = add_instrument(db)
    add_txn(db, inst, "buy", 60, 10.0, date=date(2026, 1, 1))
    with pytest.raises(HTTPException) as exc:
        create_transaction(
            TransactionCreate(instrument_id=inst.id, type="sell",
                              quantity=100, price=10.0, date=date(2026, 2, 1)),
            db)
    assert exc.value.status_code == 400
    assert "Oversell" in exc.value.detail
    # and the failed sell left no trace
    assert pf.compute_holdings(db)[0]["quantity"] == 60.0


def test_p0_2_stale_price_hides_totals(db):
    """A 1100 + B unpriced, invested 2000 -> totals must be None, not -900."""
    a = add_instrument(db, symbol="AAA")
    b = add_instrument(db, symbol="BBB")
    add_txn(db, a, "buy", 100, 10.0, date=date(2026, 1, 1))
    add_txn(db, b, "buy", 100, 10.0, date=date(2026, 1, 1))
    add_price(db, a, 11.0, date=date(2026, 3, 1))
    s = pf.portfolio_summary(db, base="USD")
    assert s.price_stale == ["BBB"]
    assert s.total_value is None
    assert s.total_pnl is None
    assert s.xirr is None


def test_sell_fee_deducted_from_proceeds(db):
    """Sell cashflow = qty*price - fee (fee used to cancel out)."""
    inst = add_instrument(db, currency="USD")
    add_txn(db, inst, "buy", 2, 100.66, fee=1.99, date=date(2026, 9, 28), fx=7.85)
    add_txn(db, inst, "sell", 2, 100.50, fee=1.99, date=date(2026, 10, 3), fx=7.85)
    add_price(db, inst, 100.50, date=date(2026, 10, 3))
    captured = []
    orig = pf.xirr
    pf.xirr = lambda cfs: (captured.extend(cfs), orig(cfs))[1]
    try:
        pf.portfolio_summary(db, base="HKD")
    finally:
        pf.xirr = orig
    flows = {d: a for d, a in captured}
    assert abs(flows[date(2026, 9, 28)] - (-(2 * 100.66 + 1.99) * 7.85)) < 0.01
    assert abs(flows[date(2026, 10, 3)] - ((2 * 100.50 - 1.99) * 7.85)) < 0.01


def test_dividend_fee_not_counted_as_profit(db):
    """Dividend 2 x 0.30 fee 0 -> +0.60, not +0.60 + fee."""
    inst = add_instrument(db, currency="USD")
    add_txn(db, inst, "buy", 2, 100.0, date=date(2026, 1, 1), fx=7.85)
    add_txn(db, inst, "dividend", 2, 0.30, fee=0.0, date=date(2026, 2, 1), fx=7.85)
    add_price(db, inst, 100.0, date=date(2026, 2, 2))
    s = pf.portfolio_summary(db, base="HKD")
    assert abs(s.realized_pnl - 0.60 * 7.85) < 0.01


def test_fx_gap_hides_totals(db):
    """When FX is unavailable, totals are None and fx_stale names the currency."""
    from app.services import portfolio as pf2
    old = pf2._fx_rates
    pf2._fx_rates = lambda: {"HKD": 1.0, "USD": None, "CNY": None}
    try:
        inst = add_instrument(db, currency="USD")
        add_txn(db, inst, "buy", 2, 100.0, date=date(2026, 1, 1))
        add_price(db, inst, 100.0, date=date(2026, 2, 1))
        s = pf2.portfolio_summary(db, base="HKD")
        assert s.total_value is None
        assert s.total_invested is None
        assert s.total_pnl is None
        assert s.xirr is None
        assert s.fx_stale == ["USD"]
    finally:
        pf2._fx_rates = old
