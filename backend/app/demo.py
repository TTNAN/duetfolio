"""Showcase dataset + read-only demo mode (for a public live demo).

DEMO_MODE=true:
- an empty database is seeded with a fictional US+HK portfolio on startup
  and its daily price history is back-filled in the background;
- every write endpoint returns 403, except price refresh/backfill and the
  CSV import *preview* (which writes nothing), so visitors can click
  around without changing the data.
"""
from __future__ import annotations

import threading
from datetime import date

from app.database import SessionLocal
from app.models.models import CashFlow, Instrument, Transaction

# fictional, illustrative trades — not anyone's real portfolio
SHOWCASE = {
    "instruments": [
        ("AAPL", "Apple Inc.", "US", "USD", "stock"),
        ("NVDA", "NVIDIA Corporation", "US", "USD", "stock"),
        ("QQQ", "Invesco QQQ Trust", "US", "USD", "etf"),
        ("SGOV", "iShares 0-3 Month Treasury Bond ETF", "US", "USD", "etf"),
        ("700.HK", "Tencent Holdings", "HK", "HKD", "stock"),
        ("2800.HK", "Tracker Fund of Hong Kong", "HK", "HKD", "etf"),
    ],
    # symbol, type, qty, price, fee, date
    "transactions": [
        ("QQQ", "buy", 20, 438.20, 1.99, date(2025, 1, 6)),
        ("700.HK", "buy", 300, 392.40, 98.0, date(2025, 1, 15)),
        ("AAPL", "buy", 40, 229.50, 1.99, date(2025, 2, 3)),
        ("2800.HK", "buy", 2000, 20.35, 45.0, date(2025, 3, 10)),
        ("NVDA", "buy", 60, 108.90, 1.99, date(2025, 4, 8)),
        ("QQQ", "buy", 10, 455.10, 1.99, date(2025, 6, 2)),
        ("700.HK", "dividend", 300, 4.13, 0.0, date(2025, 6, 4)),
        ("AAPL", "sell", 15, 241.80, 1.99, date(2025, 9, 15)),
        ("SGOV", "buy", 80, 100.52, 1.99, date(2025, 10, 1)),
        ("2800.HK", "dividend", 2000, 0.36, 0.0, date(2025, 10, 23)),
        ("NVDA", "buy", 20, 182.30, 1.99, date(2026, 1, 12)),
        ("700.HK", "buy", 100, 598.00, 70.0, date(2026, 3, 20)),
        ("SGOV", "dividend", 80, 0.35, 0.11, date(2026, 6, 3)),
    ],
    "cash": [],
}


def seed_showcase(db) -> bool:
    """Insert the showcase portfolio into an EMPTY database. Returns True if seeded."""
    if db.query(Instrument).count() > 0:
        return False
    by_sym = {}
    for sym, name, mkt, ccy, typ in SHOWCASE["instruments"]:
        by_sym[sym] = Instrument(symbol=sym, name=name, market=mkt, currency=ccy, asset_type=typ)
        db.add(by_sym[sym])
    db.flush()
    fx = {"USD": 7.80, "HKD": 1.0}
    for sym, typ, q, p, fee, d in SHOWCASE["transactions"]:
        inst = by_sym[sym]
        db.add(Transaction(instrument_id=inst.id, type=typ, quantity=q, price=p, fee=fee,
                           date=d, note="demo", fx_to_hkd=fx[inst.currency]))
    for d, direction, amount, ccy in SHOWCASE["cash"]:
        db.add(CashFlow(date=d, direction=direction, amount=amount, currency=ccy, note="demo"))
    db.commit()
    return True


def _warm_prices() -> None:
    from app.services import market
    db = SessionLocal()
    try:
        market.backfill_history(db)
        market.refresh_all(db, force=True)
    except Exception:
        pass
    finally:
        db.close()


def bootstrap() -> None:
    """Seed (if empty) and warm prices in a background thread."""
    db = SessionLocal()
    try:
        seed_showcase(db)
    finally:
        db.close()
    threading.Thread(target=_warm_prices, daemon=True).start()


# write endpoints visitors may still call in demo mode
DEMO_ALLOWED_WRITES = {
    "/api/prices/refresh",
    "/api/prices/backfill",
    "/api/transactions/import/preview",
}
