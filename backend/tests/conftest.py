"""Shared fixtures: isolated in-memory SQLite DB, FX rates mocked (no network)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Instrument, PriceSnapshot, Transaction
from app.services import portfolio as pf

# fixed rates so tests never touch the network
pf._fx_rates = lambda: {"HKD": 1.0, "USD": 7.85, "CNY": 1.09}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_instrument(db, symbol="AAA", currency="USD", market="US"):
    inst = Instrument(symbol=symbol, name=symbol, market=market,
                      currency=currency, asset_type="stock")
    db.add(inst)
    db.commit()
    return inst


def add_txn(db, inst, type, quantity, price, fee=0.0, date=None, fx=None):
    from datetime import date as d
    t = Transaction(instrument_id=inst.id, type=type, quantity=quantity,
                    price=price, fee=fee, date=date or d(2026, 1, 1),
                    fx_to_hkd=fx)
    db.add(t)
    db.commit()
    return t


def add_price(db, inst, close, date=None):
    from datetime import date as d
    s = PriceSnapshot(instrument_id=inst.id, date=date or d(2026, 3, 1),
                      close=close, source="test")
    db.add(s)
    db.commit()
    return s
