"""v0.3: splits, FIFO vs WAC, result cache, persistent quote TTL, broker CSVs."""
from datetime import date as d, datetime, timedelta, timezone

from app.models.models import PriceSnapshot
from app.services import cache
from app.services import market as mk
from app.services import portfolio as pf
from app.services.csvimport import parse_csv
from tests.conftest import add_instrument, add_price, add_txn
from tests.test_v02 import client  # noqa: F401  (fixture)


# ---------- splits ----------
def test_split_scales_shares_keeps_cost(db):
    a = add_instrument(db, "NVDA", "USD")
    add_txn(db, a, "buy", 10, 1000.0, date=d(2026, 1, 1), fx=7.8)
    add_txn(db, a, "split", 4, 0.0, date=d(2026, 2, 1))
    add_price(db, a, 260.0, date=d(2026, 3, 1))
    h = pf.compute_holdings(db)[0]
    assert h["quantity"] == 40
    assert h["invested"] == 10000.0 and h["avg_cost"] == 250.0
    s = pf.portfolio_summary(db, base="USD")
    assert abs(s.unrealized_pnl - (40 * 260 - 10000)) < 0.01


def test_split_then_sell_all_is_not_oversell(client, monkeypatch):  # noqa: F811
    i = client.post("/api/instruments", json={"symbol": "TSLA", "market": "US",
                                               "currency": "USD", "asset_type": "stock"}).json()
    monkeypatch.setattr(mk, "backfill_history",
                        lambda *a, **k: {"filled": [], "failed": [], "inserted": 0})
    post = lambda **b: client.post("/api/transactions", json={"instrument_id": i["id"], **b})
    assert post(type="buy", quantity=5, price=600, date="2026-01-02").status_code == 201
    r = post(type="split", quantity=3, price=99, date="2026-02-01")
    assert r.status_code == 201 and r.json()["price"] == 0.0     # price ignored for splits
    assert post(type="sell", quantity=15, price=200, date="2026-03-01").status_code == 201
    assert post(type="sell", quantity=1, price=200, date="2026-03-02").status_code == 400


def test_history_values_pre_split_days_with_adjusted_prices(db):
    a = add_instrument(db, "AAA", "USD")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    add_txn(db, a, "split", 2, 0.0, date=d(2026, 1, 3))
    # split-adjusted daily closes (what Yahoo returns): 50 throughout
    for day in (1, 2, 3, 4):
        add_price(db, a, 50.0, date=d(2026, 1, day))
    hist = pf.portfolio_history(db, base="USD")
    assert [p.value for p in hist] == [1000.0] * 4      # no fake -50% drop / jump
    assert abs(hist[-1].twr) < 1e-9


# ---------- FIFO vs WAC ----------
def _two_lots(db):
    a = add_instrument(db, "AAA", "USD")
    add_txn(db, a, "buy", 10, 10.0, date=d(2026, 1, 1))
    add_txn(db, a, "buy", 10, 20.0, date=d(2026, 1, 2))
    add_txn(db, a, "sell", 10, 25.0, date=d(2026, 1, 3))
    add_price(db, a, 25.0, date=d(2026, 1, 4))
    return a


def test_fifo_vs_wac_realized_and_basis(db):
    _two_lots(db)
    wac = pf.compute_holdings(db, "wac")[0]
    fifo = pf.compute_holdings(db, "fifo")[0]
    assert wac["realized_pnl"] == 100.0 and wac["invested"] == 150.0     # avg 15
    assert fifo["realized_pnl"] == 150.0 and fifo["invested"] == 200.0   # sold the 10s
    # total P&L is the same either way; only the realized/unrealized split moves
    s_w = pf.portfolio_summary(db, base="USD", method="wac")
    s_f = pf.portfolio_summary(db, base="USD", method="fifo")
    assert s_f.cost_method == "fifo"
    assert abs(s_w.total_pnl - s_f.total_pnl) < 0.01
    assert s_w.xirr == s_f.xirr


def test_fifo_lot_survives_split(db):
    a = add_instrument(db, "AAA", "USD")
    add_txn(db, a, "buy", 10, 10.0, date=d(2026, 1, 1))
    add_txn(db, a, "buy", 10, 30.0, date=d(2026, 1, 2))
    add_txn(db, a, "split", 2, 0.0, date=d(2026, 1, 3))
    add_txn(db, a, "sell", 20, 10.0, date=d(2026, 1, 4))   # = the first lot, now at 5/share
    add_price(db, a, 10.0, date=d(2026, 1, 5))
    h = pf.compute_holdings(db, "fifo")[0]
    assert h["realized_pnl"] == 100.0 and h["invested"] == 300.0


# ---------- result cache ----------
def test_cache_invalidates_on_write(db):
    a = add_instrument(db, "AAA", "USD")
    add_txn(db, a, "buy", 1, 100.0, date=d(2026, 1, 1))
    add_price(db, a, 110.0, date=d(2026, 1, 2))
    v1 = cache.data_version(db)
    s1 = pf.portfolio_summary(db, base="USD")
    assert pf.portfolio_summary(db, base="USD").total_value == s1.total_value
    add_txn(db, a, "buy", 1, 100.0, date=d(2026, 1, 2))
    assert cache.data_version(db) > v1
    assert pf.portfolio_summary(db, base="USD").total_value == 220.0
    # edits (not just inserts) invalidate too
    snap = db.query(PriceSnapshot).first()
    snap.close = 120.0
    db.commit()
    assert pf.portfolio_summary(db, base="USD").total_value == 240.0


def test_cached_result_is_not_shared_mutably(db):
    a = add_instrument(db, "AAA", "USD")
    add_txn(db, a, "buy", 1, 100.0)
    add_price(db, a, 110.0)
    s = pf.portfolio_summary(db, base="USD")
    s.holdings[0].symbol = "HACKED"
    assert pf.portfolio_summary(db, base="USD").holdings[0].symbol == "AAA"


# ---------- persistent quote TTL ----------
def test_refresh_skips_fresh_quotes(db, monkeypatch):
    a = add_instrument(db, "AAA", "USD")
    b = add_instrument(db, "BBB", "USD")
    now = datetime.now(timezone.utc)
    db.add(PriceSnapshot(instrument_id=a.id, date=d.today(), close=1.0, source="t",
                         fetched_at=now - timedelta(seconds=30)))
    db.add(PriceSnapshot(instrument_id=b.id, date=d.today() - timedelta(days=1), close=1.0,
                         source="t", fetched_at=now - timedelta(hours=2)))
    db.commit()
    calls = []

    class P(mk.BaseProvider):
        name = "fake"

        def fetch_close(self, symbol):
            calls.append(symbol)
            return (d.today(), 2.0, 1.0)

    monkeypatch.setattr(mk, "get_provider", lambda: P())
    monkeypatch.setattr(mk, "YFinanceProvider", P)
    monkeypatch.setattr(mk, "EastMoneyProvider", P)
    monkeypatch.setattr(mk, "SinaProvider", P)
    r = mk.refresh_all(db)
    assert r["fresh"] == ["AAA"] and r["updated"] == ["BBB"] and calls == ["BBB"]
    calls.clear()
    r = mk.refresh_all(db, force=True)
    assert sorted(calls) == ["AAA", "BBB"]


# ---------- broker CSV presets ----------
def _ok(res):
    return [r for r in res["rows"] if r["status"] == "ok"]


def test_futu_prefers_filled_columns_and_market_labels():
    csv_ = ("方向,代码,名称,订单价格,订单数量,成交数量,成交价格,成交金额,下单时间,成交时间,市场,合计费用\n"
            "买入,00700,腾讯控股,380,200,100,379.8,37980,2026-09-01 09:30:00,2026-09-01 09:31:02,港股,52.3\n"
            "卖出,AAPL,苹果,230,10,10,231.5,2315,2026-09-02 22:00:00,2026-09-02 22:00:05,美股,1.99\n")
    rows = _ok(parse_csv(csv_.encode("utf-8"), broker="futu"))
    assert rows[0]["symbol"] == "700.HK" and rows[0]["quantity"] == 100
    assert rows[0]["price"] == 379.8 and rows[0]["fee"] == 52.3
    assert rows[1]["symbol"] == "AAPL" and rows[1]["type"] == "sell" and rows[1]["market"] == "US"


def test_tiger_sums_itemized_fees():
    csv_ = ("股票代码,交易方向,成交数量,成交价格,成交时间,佣金,平台费,交收费\n"
            "TSLA,买入,5,250.00,2026-08-03 21:35:00,0.99,1.00,0.15\n").encode("gbk")
    rows = _ok(parse_csv(csv_))
    assert rows[0]["symbol"] == "TSLA" and abs(rows[0]["fee"] - 2.14) < 1e-9


def test_schwab_transactions_export():
    csv_ = ('"Transactions  for account XXXX-1234 as of 10/14/2026"\n'
            '"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n'
            '"10/01/2026","Buy","QQQ","INVESCO QQQ TRUST","3","$480.10","","-$1,440.30"\n'
            '"10/02/2026 as of 10/01/2026","Sell","AAPL","APPLE INC","2","$231.00","$0.02","$461.98"\n'
            '"09/30/2026","Qualified Dividend","SCHD","SCHWAB US DIVIDEND","","","","$12.34"\n'
            '"09/30/2026","NRA Tax Adj","SCHD","SCHWAB US DIVIDEND","","","","-$1.23"\n'
            '"09/29/2026","MoneyLink Transfer","","Tfr BANK","","","","$5,000.00"\n'
            '"Transactions Total","","","","","","","$4,032.79"\n')
    res = parse_csv(csv_.encode())
    assert res["format"] == "schwab"
    ok = _ok(res)
    assert [(r["type"], r["symbol"]) for r in ok] == [("buy", "QQQ"), ("sell", "AAPL"), ("dividend", "SCHD")]
    assert ok[0]["price"] == 480.10 and ok[1]["fee"] == 0.02 and ok[1]["date"] == "2026-10-02"
    assert ok[2]["quantity"] * ok[2]["price"] == 12.34
    assert sum(r["status"] == "skip" for r in res["rows"]) == 2


def test_broker_param_on_preview(client):  # noqa: F811
    csv_ = b"Symbol,Side,Quantity,Price,Date\nAAPL,BUY,1,100,2026-01-02\n"
    r = client.post("/api/transactions/import/preview?broker=generic",
                    files={"file": ("t.csv", csv_, "text/csv")})
    assert r.status_code == 200 and r.json()["format"] == "generic"
    assert r.json()["rows"][0]["status"] == "ok"
