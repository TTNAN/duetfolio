"""REST API: instruments, transactions, portfolio, price refresh."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models.models import Instrument, Transaction
from app.schemas.schemas import (
    HistoryPoint, HoldingOut, InstrumentCandidate, InstrumentCreate, InstrumentOut,
    PortfolioSummary, TransactionCreate, TransactionOut, TransactionUpdate,
)
from app.services import market
from app.services.portfolio import compute_holdings, latest_price, portfolio_history, portfolio_summary

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "base_currency": config.BASE_CURRENCY}


# ---- instruments ----
@router.get("/instruments/search", response_model=list[InstrumentCandidate])
def search_instruments(q: str = Query(..., min_length=1, max_length=50)):
    """Symbol search for the add-instrument box: Yahoo + East Money suggest,
    normalized to Yahoo-format tickers. Either source failing degrades
    gracefully to the other."""
    return market.search_instruments(q)


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
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction, Instrument.symbol).join(
        Instrument, Transaction.instrument_id == Instrument.id
    )
    if instrument_id:
        q = q.filter(Transaction.instrument_id == instrument_id)
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    q = q.offset(offset).limit(limit)
    return [
        TransactionOut(
            id=t.id, instrument_id=t.instrument_id, type=t.type,
            quantity=t.quantity, price=t.price, fee=t.fee,
            date=t.date, note=t.note, fx_to_hkd=t.fx_to_hkd, symbol=symbol,
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
    fx_to_hkd = market.fetch_fx_to_hkd(inst.currency, body.date)
    t = Transaction(**body.model_dump(), fx_to_hkd=fx_to_hkd)
    db.add(t)
    db.commit()
    db.refresh(t)
    return TransactionOut(
        id=t.id, instrument_id=t.instrument_id, type=t.type,
        quantity=t.quantity, price=t.price, fee=t.fee,
        date=t.date, note=t.note, fx_to_hkd=t.fx_to_hkd, symbol=inst.symbol,
    )


@router.put("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, body: TransactionUpdate,
                       db: Session = Depends(get_db)):
    t = db.get(Transaction, transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    inst = db.get(Instrument, t.instrument_id)
    for field in ("type", "quantity", "price", "fee", "date", "note"):
        v = getattr(body, field)
        if v is not None:
            setattr(t, field, v)
    # FX: keep the original rate unless the user explicitly asks to refetch
    # for the (possibly new) date — otherwise a typo fix on price would
    # silently re-rate the cashflow at today's FX.
    if body.refetch_fx:
        t.fx_to_hkd = market.fetch_fx_to_hkd(inst.currency, t.date)
    db.flush()
    # oversell guard: the edit must not leave any instrument with negative
    # net quantity (compute_holdings clamps negatives to 0, so count raw)
    from collections import defaultdict
    qty_by_inst: dict[int, float] = defaultdict(float)
    for iid, typ, q in db.query(
            Transaction.instrument_id, Transaction.type, Transaction.quantity).all():
        if typ == "buy":
            qty_by_inst[iid] += q
        elif typ == "sell":
            qty_by_inst[iid] -= q
    bad_id = next((i for i, q in qty_by_inst.items() if q < -1e-9), None)
    if bad_id is not None:
        db.rollback()
        bad_inst = db.get(Instrument, bad_id)
        raise HTTPException(
            400, f"Oversell: edit would leave "
                 f"{bad_inst.symbol} at {qty_by_inst[bad_id]:g}")
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


@router.get("/portfolio/history", response_model=list[HistoryPoint])
def get_history(
    base: str = Query(default=config.BASE_CURRENCY, pattern="^(HKD|USD|CNY)$"),
    db: Session = Depends(get_db),
):
    return portfolio_history(db, base=base)


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
