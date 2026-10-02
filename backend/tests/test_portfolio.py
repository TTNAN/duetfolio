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
    mk.fetch_fx_to_hkd = lambda *a: 7.85  # no network in tests
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


def test_history_values_from_snapshots(db):
    """History = qty-on-day x carried-forward close, converted to base."""
    from datetime import date as d
    a = add_instrument(db, "AAA", "USD", "US")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    add_price(db, a, 110.0, date=d(2026, 1, 5))
    add_price(db, a, 120.0, date=d(2026, 1, 10))
    pts = pf.portfolio_history(db, base="HKD")
    assert [(p.date, p.value) for p in pts] == [
        (d(2026, 1, 5), round(10 * 110.0 * 7.85, 2)),
        (d(2026, 1, 10), round(10 * 120.0 * 7.85, 2)),
    ]


def test_history_carry_forward_and_sell(db):
    """Missing days carry the last close; sells reduce quantity mid-series."""
    from datetime import date as d
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    add_txn(db, a, "sell", 4, 100.0, date=d(2026, 1, 8))
    add_price(db, a, 100.0, date=d(2026, 1, 5))
    add_price(db, a, 110.0, date=d(2026, 1, 10))
    pts = pf.portfolio_history(db, base="HKD")
    assert [(p.date, p.value) for p in pts] == [
        (d(2026, 1, 5), 10 * 100.0),   # 10 shares @100
        (d(2026, 1, 10), 6 * 110.0),   # 6 shares @110 after the sell
    ]


def test_xirr_uses_latest_price_date_not_today(db):
    """Terminal XIRR cashflow is dated at the latest price, not today,
    so stale prices don't inflate the annualized rate."""
    from datetime import date as d, timedelta
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    old = d.today() - timedelta(days=30)
    add_price(db, a, 110.0, date=old)
    s = pf.portfolio_summary(db, base="HKD")
    # XIRR with terminal dated at `old` must equal the manual calc
    from app.services.xirr import xirr as calc
    expect = calc([(d(2026, 1, 1), -1000.0), (old, 1100.0)])
    # note: summary rounds XIRR to 4 decimals
    assert s.xirr is not None and abs(s.xirr - expect) < 1e-4
    # sanity: dating the terminal at today instead would give a lower rate
    wrong = calc([(d(2026, 1, 1), -1000.0), (d.today(), 1100.0)])
    assert abs(wrong - expect) > 1e-6


def test_history_fx_gap_gives_none(db):
    """When FX is unavailable, history points are None rather than wrong."""
    from datetime import date as d
    pf._fx_rates = lambda: {"HKD": 1.0, "USD": None, "CNY": None}
    try:
        a = add_instrument(db, "AAA", "USD", "US")
        add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
        add_price(db, a, 110.0, date=d(2026, 1, 5))
        pts = pf.portfolio_history(db, base="HKD")
        assert len(pts) == 1 and pts[0].value is None
    finally:
        from tests.conftest import pf as _pf  # restore fixed rates
        _pf._fx_rates = lambda: {"HKD": 1.0, "USD": 7.85, "CNY": 1.09}


def test_update_txn_keeps_fx_unless_refetch(db):
    """Inline edit preserves fx_to_hkd; refetch_fx re-rates at the new date."""
    from datetime import date as d
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.routes as routes

    a = add_instrument(db, "AAA", "USD", "US")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1), fx=7.80)

    # bypass TestClient's own DB: call the route function with our session
    t = db.query(__import__("app.models.models", fromlist=["Transaction"]).Transaction).first()
    body = __import__("app.schemas.schemas", fromlist=["TransactionUpdate"]).TransactionUpdate(
        price=101.0)
    out = routes.update_transaction(t.id, body, db)
    assert out.price == 101.0 and out.fx_to_hkd == 7.80  # kept

    body2 = __import__("app.schemas.schemas", fromlist=["TransactionUpdate"]).TransactionUpdate(
        date=d(2026, 2, 1), refetch_fx=True)
    out2 = routes.update_transaction(t.id, body2, db)
    assert out2.date == d(2026, 2, 1)
    # refetched via mocked _fx_rates -> 7.85 (module-level mock in conftest)
    assert out2.fx_to_hkd == 7.85


def test_update_txn_oversell_rejected(db):
    """Editing a buy down below sold quantity is rejected with 400."""
    from datetime import date as d
    from fastapi import HTTPException
    import app.api.routes as routes

    a = add_instrument(db, "AAA", "USD", "US")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    add_txn(db, a, "sell", 6, 110.0, date=d(2026, 2, 1))
    t = db.query(__import__("app.models.models", fromlist=["Transaction"]).Transaction).filter_by(type="buy").first()
    TU = __import__("app.schemas.schemas", fromlist=["TransactionUpdate"]).TransactionUpdate
    try:
        routes.update_transaction(t.id, TU(quantity=5.0), db)
        raise AssertionError("should have raised")
    except HTTPException as e:
        assert e.status_code == 400


def test_cash_flows_enter_xirr(db):
    """Deposits are XIRR outflows (negative), withdrawals inflows."""
    from datetime import date as d
    from app.models.models import CashFlow
    a = add_instrument(db, "AAA", "HKD", "HK")
    db.add(CashFlow(date=d(2026, 1, 1), direction="in", amount=10000.0, currency="HKD"))
    db.commit()
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 2))
    add_price(db, a, 110.0, date=d(2026, 6, 1))
    s = pf.portfolio_summary(db, base="HKD")
    from app.services.xirr import xirr as calc
    expect = calc([(d(2026, 1, 1), -10000.0), (d(2026, 1, 2), -1000.0), (d(2026, 6, 1), 1100.0)])
    assert s.xirr is not None and abs(s.xirr - expect) < 1e-4


def test_day_change_fields(db):
    """prev_close -> day change amount, pct, and base-currency P&L."""
    from datetime import date as d
    from app.models.models import PriceSnapshot
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    db.add(PriceSnapshot(instrument_id=a.id, date=d(2026, 3, 1), close=110.0,
                         prev_close=100.0, source="test"))
    db.commit()
    s = pf.portfolio_summary(db, base="HKD")
    h = s.holdings[0]
    assert h.day_change == 10.0
    assert abs(h.day_change_pct - 0.1) < 1e-9
    assert h.day_change_base == 100.0  # 10 shares x 10
    assert h.weight_pct == 100.0


def test_csv_preview_table_and_ibkr():
    from app.services.csvimport import parse_csv
    futu = ("市场,证券代码,买卖方向,成交数量,成交价格,成交时间,手续费\n"
            "HK,00700,买入,100,388.00,2026-09-01 09:31:00,15.00\n").encode("gbk")
    r = parse_csv(futu)
    assert r["format"] == "table"
    row = r["rows"][0]
    assert row["status"] == "ok" and row["symbol"] == "700.HK"
    assert row["type"] == "buy" and row["quantity"] == 100.0
    ibkr = ('Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,Comm/Fee,Exchange\n'
            'Trades,Data,Order,Stocks,USD,AAPL,"2026-09-30, 13:00:00",-10,232.5,-1,NASDAQ\n').encode()
    r2 = parse_csv(ibkr)
    row2 = r2["rows"][0]
    assert row2["status"] == "ok" and row2["symbol"] == "AAPL" and row2["type"] == "sell"


def test_search_hk_not_crowded_out(monkeypatch):
    """'博时' must surface 3152.HK: the mktnum=116 query rescues HK ETFs
    that mainland funds crowd out of the unfiltered ranking."""
    from app.services import market as m

    def fake_get(url, timeout=None):
        if "mktnum=116" in url:
            items = [
                {"Code": "02832", "Name": "博时科创50", "MktNum": "116"},
                {"Code": "03152", "Name": "A博时港元", "MktNum": "116"},
            ]
        elif "query1.finance.yahoo.com" in url:
            return {}
        else:
            items = [
                {"Code": "160505", "Name": "博时主题LOF", "MktNum": "0", "Classify": "Fund"},
                {"Code": "02832", "Name": "博时科创50", "MktNum": "116"},
            ]
        return {"QuotationCodeTable": {"Data": items}}

    monkeypatch.setattr(m, "_http_get_json", fake_get)
    res = m.search_instruments("博时")
    syms = [r["symbol"] for r in res]
    assert "3152.HK" in syms
    assert "2832.HK" in syms
    assert syms.count("2832.HK") == 1  # deduped across the two queries
    assert not any(r["market"] not in ("HK", "US") for r in res)


def test_refresh_falls_back_to_backup_provider(db, monkeypatch):
    """Primary (eastmoney) returns nothing -> yahoo quote is used and the
    snapshot records the actual source."""
    from datetime import date as d
    from app.services import market as m
    from app.models.models import PriceSnapshot

    inst = add_instrument(db, "SGOV", "USD", "US")
    monkeypatch.setattr(m.EastMoneyProvider, "fetch_close",
                        lambda self, sym: None)
    monkeypatch.setattr(m.YFinanceProvider, "fetch_close",
                        lambda self, sym: (d(2026, 10, 2), 100.5, 100.4))
    monkeypatch.setattr(m.SinaProvider, "fetch_close",
                        lambda self, sym: None)
    monkeypatch.setattr(m.config, "MARKET_PROVIDER", "eastmoney")

    res = m.refresh_all(db)
    assert res["provider"] == "eastmoney"
    assert res["fallbacks"] == ["yfinance", "sina"]
    assert res["updated"] == ["SGOV"] and not res["failed"]
    snap = db.query(PriceSnapshot).filter_by(instrument_id=inst.id).one()
    assert snap.close == 100.5 and snap.source == "yfinance"


def test_refresh_all_providers_fail(db, monkeypatch):
    from app.services import market as m

    add_instrument(db, "SGOV", "USD", "US")
    monkeypatch.setattr(m.EastMoneyProvider, "fetch_close",
                        lambda self, sym: None)
    monkeypatch.setattr(m.SinaProvider, "fetch_close",
                        lambda self, sym: None)
    monkeypatch.setattr(m.YFinanceProvider, "fetch_close",
                        lambda self, sym: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(m.config, "MARKET_PROVIDER", "eastmoney")

    res = m.refresh_all(db)
    assert res["failed"] == ["SGOV"] and not res["updated"]
