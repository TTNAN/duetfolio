"""REST API: instruments, transactions, portfolio, price refresh."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models.models import Instrument, Transaction
from app.schemas.schemas import (
    HoldingOut, InstrumentCreate, InstrumentOut, PortfolioSummary,
    TransactionCreate, TransactionOut,
)
from app.services import market
from app.services.portfolio import compute_holdings, latest_price, portfolio_summary

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "base_currency": config.BASE_CURRENCY}


# ---- instruments ----
@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(db: Session = Depends(get_db)):
    return db.query(Instrument).order_by(Instrument.symbol).all()


@router.post("/instruments", response_model=InstrumentOut, status_code=201)
def create_instrument(body: InstrumentCreate, db: Session = Depends(get_db)):
    if db.query(Instrument).filter_by(symbol=body.symbol).first():
        raise HTTPException(400, f"Instrument {body.symbol} already exists")
    inst = Instrument(**body.model_dump())
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


@router.delete("/instruments/{instrument_id}", status_code=204)
def delete_instrument(instrument_id: int, db: Session = Depends(get_db)):
    inst = db.get(Instrument, instrument_id)
    if not inst:
        raise HTTPException(404, "Instrument not found")
    db.delete(inst)
    db.commit()


# ---- transactions ----
@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    instrument_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction, Instrument.symbol).join(
        Instrument, Transaction.instrument_id == Instrument.id
    )
    if instrument_id:
        q = q.filter(Transaction.instrument_id == instrument_id)
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    return [
        TransactionOut(
            id=t.id, instrument_id=t.instrument_id, type=t.type,
            quantity=t.quantity, price=t.price, fee=t.fee,
            date=t.date, note=t.note, symbol=symbol,
        )
        for t, symbol in q.all()
    ]


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionCreate, db: Session = Depends(get_db)):
    inst = db.get(Instrument, body.instrument_id)
    if not inst:
        raise HTTPException(400, "Unknown instrument_id")
    if body.type == "sell":
        held = next(
            (h["quantity"] for h in compute_holdings(db)
             if h["instrument"].id == body.instrument_id), 0.0)
        if body.quantity > held + 1e-9:
            raise HTTPException(
                400, f"Oversell: holding {held:g}, tried to sell {body.quantity:g}")
    # capture the FX rate of the transaction date so historical cashflows
    # (XIRR) aren't polluted by later FX moves; None = fall back to current
    fx_to_hkd = market.fetch_fx_to_hkd_on(inst.currency, body.date)
    t = Transaction(**body.model_dump(), fx_to_hkd=fx_to_hkd)
    db.add(t)
    db.commit()
    db.refresh(t)
    return TransactionOut(
        id=t.id, instrument_id=t.instrument_id, type=t.type,
        quantity=t.quantity, price=t.price, fee=t.fee,
        date=t.date, note=t.note, fx_to_hkd=t.fx_to_hkd, symbol=inst.symbol,
    )


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    t = db.get(Transaction, transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    db.delete(t)
    db.commit()


# ---- portfolio ----
@router.get("/portfolio/summary", response_model=PortfolioSummary)
def get_summary(
    base: str = Query(default=config.BASE_CURRENCY, pattern="^(HKD|USD|CNY)$"),
    db: Session = Depends(get_db),
):
    return portfolio_summary(db, base=base)


@router.get("/portfolio/holdings", response_model=list[HoldingOut])
def get_holdings(
    base: str = Query(default=config.BASE_CURRENCY, pattern="^(HKD|USD|CNY)$"),
    db: Session = Depends(get_db),
):
    return portfolio_summary(db, base=base).holdings


# ---- market data ----
@router.post("/prices/refresh")
def refresh_prices(db: Session = Depends(get_db)):
    """Pull latest closes from Yahoo Finance for all instruments."""
    return market.refresh_all(db)
