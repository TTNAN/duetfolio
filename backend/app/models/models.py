"""Domain models.

Design notes (deliberate scope choices):
- Single user, no auth. Auth would be the next milestone, not this one.
- Transactions are the source of truth. Holdings are always derived,
  never stored. Market data snapshots are a cache, not canonical state.
- `Instrument.symbol` is stored as a Yahoo Finance ticker (e.g. "SGOV",
  "03152.HK") so the price pipeline needs no symbol translation layer.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False, default="")
    market = Column(String(8), nullable=False, default="US")      # US | HK
    currency = Column(String(8), nullable=False, default="USD")   # USD | HKD
    asset_type = Column(String(16), nullable=False, default="etf")  # stock | etf | fund
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    transactions = relationship("Transaction", back_populates="instrument", cascade="all, delete-orphan")
    prices = relationship("PriceSnapshot", back_populates="instrument", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    type = Column(String(16), nullable=False)  # buy | sell | dividend
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)  # per-share, in instrument currency
    fee = Column(Float, nullable=False, default=0.0)
    date = Column(Date, nullable=False, index=True)
    note = Column(Text, default="")
    # HKD per 1 unit of instrument currency, captured on the transaction date.
    # Used to convert historical cashflows (XIRR) at the rate of the time,
    # so FX moves don't leak into "investment return". NULL = fall back to
    # the current rate (pre-feature data).
    fx_to_hkd = Column(Float, nullable=True)

    instrument = relationship("Instrument", back_populates="transactions")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (UniqueConstraint("instrument_id", "date", name="uq_price_instrument_date"),)

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    close = Column(Float, nullable=False)  # in instrument currency
    source = Column(String(32), default="yfinance", nullable=False)

    instrument = relationship("Instrument", back_populates="prices")
