"""Seed demo data: two real trades (ZA Bank coupon arbitrage, 2026-09/10).

Usage:
    cd backend
    .venv/bin/python seed_demo.py        # creates tables if needed, inserts demo rows
"""
from datetime import date

from app.database import Base, SessionLocal, engine
from app.models.models import Instrument, Transaction


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(Instrument).count() > 0:
            print("Database already has instruments, skipping seed.")
            return

        sgov = Instrument(symbol="SGOV", name="iShares 0-3 Month Treasury Bond ETF",
                          market="US", currency="USD", asset_type="etf")
        hkmm = Instrument(symbol="3152.HK", name="Bosera HKD Money Market ETF",
                          market="HK", currency="HKD", asset_type="etf")
        db.add_all([sgov, hkmm])
        db.flush()

        db.add_all([
            Transaction(instrument_id=sgov.id, type="buy", quantity=2,
                        price=100.66, fee=1.99, date=date(2026, 9, 28),
                        note="ZA Bank US coupon trade"),
            Transaction(instrument_id=hkmm.id, type="buy", quantity=9,
                        price=1134.65, fee=18.3, date=date(2026, 10, 2),
                        note="ZA Bank HK coupon trade"),
        ])
        db.commit()
        print("Seeded: SGOV x2 + 3152.HK x9. Now run: POST /api/prices/refresh")
    finally:
        db.close()


if __name__ == "__main__":
    main()
