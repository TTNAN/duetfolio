"""v0.2: TWR history, cost line, per-holding XIRR, day P&L, backfill, backup."""
from datetime import date as d

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.models import PriceSnapshot
from app.services import market as mk
from app.services import portfolio as pf
from tests.conftest import add_instrument, add_price, add_txn


def test_twr_ignores_new_money(db):
    """Doubling the position at the same price must not show as a return."""
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    add_price(db, a, 100.0, date=d(2026, 1, 1))
    add_price(db, a, 110.0, date=d(2026, 1, 2))           # +10%
    add_txn(db, a, "buy", 10, 110.0, date=d(2026, 1, 3))  # new money
    add_price(db, a, 110.0, date=d(2026, 1, 3))           # flat day
    add_price(db, a, 121.0, date=d(2026, 1, 4))           # +10%
    pts = pf.portfolio_history(db, base="HKD")
    assert [p.date for p in pts] == [d(2026, 1, d_) for d_ in (1, 2, 3, 4)]
    assert pts[1].twr == pytest.approx(0.10)
    assert pts[2].twr == pytest.approx(0.10)
    assert pts[3].twr == pytest.approx(0.21)              # 1.1 * 1.1 - 1
    assert pts[3].value == 20 * 121.0
    assert pts[3].cost == 1000.0 + 1100.0


def test_history_skips_days_before_first_trade(db):
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_price(db, a, 90.0, date=d(2025, 12, 1))   # backfilled, pre-trade
    add_txn(db, a, "buy", 1, 100.0, date=d(2026, 1, 1))
    add_price(db, a, 100.0, date=d(2026, 1, 1))
    pts = pf.portfolio_history(db, base="HKD")
    assert [p.date for p in pts] == [d(2026, 1, 1)]


def test_holding_pnl_pct_xirr_and_day_pnl(db):
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_txn(db, a, "buy", 10, 100.0, date=d(2026, 1, 1))
    db.add(PriceSnapshot(instrument_id=a.id, date=d(2027, 1, 1), close=110.0,
                         prev_close=100.0, source="test"))
    db.commit()
    s = pf.portfolio_summary(db, base="HKD")
    h = s.holdings[0]
    assert h.unrealized_pnl_pct == pytest.approx(0.10)
    assert h.xirr == pytest.approx(0.10, abs=1e-3)       # exactly one year
    assert s.day_pnl == 100.0
    assert s.day_pnl_pct == pytest.approx(0.10)          # 100 / 1000


def test_backfill_inserts_missing_days_only(db, monkeypatch):
    a = add_instrument(db, "AAA", "HKD", "HK")
    add_txn(db, a, "buy", 1, 100.0, date=d(2026, 1, 1))
    live = PriceSnapshot(instrument_id=a.id, date=d(2026, 1, 2), close=999.0,
                         prev_close=1.0, source="yfinance")
    db.add(live)
    db.commit()
    monkeypatch.setattr(mk, "fetch_daily_history", lambda sym, start: (
        [(d(2026, 1, 1), 100.0), (d(2026, 1, 2), 101.0), (d(2026, 1, 5), 102.0)], "yfinance"))
    r = mk.backfill_history(db)
    assert r == {"filled": ["AAA"], "failed": [], "inserted": 2}
    rows = {s.date: s for s in db.query(PriceSnapshot).all()}
    assert rows[d(2026, 1, 2)].close == 999.0             # live quote untouched
    assert rows[d(2026, 1, 5)].source == "yfinance-hist"


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    from app.api.routes import router
    app = FastAPI()
    app.include_router(router, prefix="/api")

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()
    app.dependency_overrides[get_db] = _db
    mk.fetch_fx_to_hkd = lambda *a, **k: 7.85
    return TestClient(app)


def test_backup_roundtrip(client):
    i = client.post("/api/instruments", json={"symbol": "AAPL", "name": "Apple",
                                               "market": "US", "currency": "USD",
                                               "asset_type": "stock"}).json()
    client.post("/api/transactions", json={"instrument_id": i["id"], "type": "buy",
                                            "quantity": 3, "price": 200, "fee": 1,
                                            "date": "2026-02-01"})
    client.post("/api/cash", json={"date": "2026-01-31", "direction": "in",
                                    "amount": 5000, "currency": "HKD"})
    backup = client.get("/api/backup").content
    csv_text = client.get("/api/transactions/export.csv").text
    assert "AAPL" in csv_text and "buy" in csv_text
    client.delete(f"/api/instruments/{i['id']}")
    assert client.get("/api/transactions").json() == []
    r = client.post("/api/backup/restore", files={"file": ("b.json", backup, "application/json")})
    assert r.json() == {"instruments": 1, "transactions": 1, "cash_flows": 1}
    tx = client.get("/api/transactions").json()
    assert tx[0]["symbol"] == "AAPL" and tx[0]["fx_to_hkd"] == 7.85
    bad = client.post("/api/backup/restore", files={"file": ("x.json", b"{}", "application/json")})
    assert bad.status_code == 400
    assert len(client.get("/api/transactions").json()) == 1  # nothing wiped


def test_patch_instrument_name(client):
    i = client.post("/api/instruments", json={"symbol": "SGOV"}).json()
    r = client.patch(f"/api/instruments/{i['id']}", json={"name": "Treasury 0-3M"})
    assert r.json()["name"] == "Treasury 0-3M"


def test_yahoo_ticker_pads_hk_codes():
    assert mk.yahoo_ticker("700.HK") == "0700.HK"
    assert mk.yahoo_ticker("5.HK") == "0005.HK"
    assert mk.yahoo_ticker("3152.HK") == "3152.HK"
    assert mk.yahoo_ticker("09988.HK") == "9988.HK"
    assert mk.yahoo_ticker("aapl") == "AAPL"
