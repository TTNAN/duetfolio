"""REST API: instruments, transactions, portfolio, price refresh."""
from datetime import date as date_cls

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models.models import CashFlow, Instrument, Transaction
from app.schemas.schemas import (
    CashFlowCreate, CashFlowOut, HistoryPoint, HoldingOut, InstrumentCandidate,
    InstrumentCreate, InstrumentOut, PortfolioSummary, TransactionCreate,
    TransactionOut, TransactionUpdate,
)
from app.services import market
from app.services.csvimport import parse_csv
from app.services.portfolio import compute_holdings, latest_price, portfolio_history, portfolio_summary

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "base_currency": config.BASE_CURRENCY,
            "market_provider": config.MARKET_PROVIDER}


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


# ---- broker CSV import ----
@router.post("/transactions/import/preview")
async def import_preview(file: UploadFile = File(...)):
    """Parse a broker CSV (Futu / IBKR / generic) -> row-by-row preview.

    Nothing is written. The frontend shows the preview and posts back
    {"rows": [...]} to /transactions/import for the confirmed rows.
    """
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5MB)")
    return parse_csv(raw)


@router.post("/transactions/import")
def import_confirm(payload: dict, db: Session = Depends(get_db)):
    """Import previewed rows. Unknown symbols auto-create instruments."""
    rows = payload.get("rows") or []
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    if not ok_rows:
        raise HTTPException(400, "No importable rows")
    inst_cache: dict[str, Instrument] = {
        i.symbol: i for i in db.query(Instrument).all()
    }
    created_insts, imported, errors = 0, 0, []
    for r in ok_rows:
        try:
            sym = r["symbol"]
            inst = inst_cache.get(sym)
            if not inst:
                inst = Instrument(
                    symbol=sym, name=r.get("name") or sym,
                    market=r.get("market", "US"), currency=r.get("currency", "USD"),
                    asset_type="stock",
                )
                db.add(inst)
                db.flush()
                inst_cache[sym] = inst
                created_insts += 1
            d = date_cls.fromisoformat(r["date"])
            fx = market.fetch_fx_to_hkd(inst.currency, d)
            db.add(Transaction(
                instrument_id=inst.id, type=r["type"],
                quantity=float(r["quantity"]), price=float(r["price"]),
                fee=float(r.get("fee") or 0.0), date=d,
                note="csv-import", fx_to_hkd=fx,
            ))
            imported += 1
        except Exception as e:
            errors.append({"lineno": r.get("lineno"), "reason": str(e)[:120]})
    db.commit()
    return {"imported": imported, "instruments_created": created_insts,
            "errors": errors}


# ---- cash flows ----


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


# ---- cash flows ----
@router.get("/cash", response_model=list[CashFlowOut])
def list_cash(db: Session = Depends(get_db)):
    return db.query(CashFlow).order_by(CashFlow.date.desc(), CashFlow.id.desc()).all()


@router.post("/cash", response_model=CashFlowOut, status_code=201)
def add_cash(body: CashFlowCreate, db: Session = Depends(get_db)):
    if body.direction not in ("in", "out"):
        raise HTTPException(400, "direction must be 'in' or 'out'")
    cf = CashFlow(**body.model_dump())
    db.add(cf)
    db.commit()
    db.refresh(cf)
    return cf


@router.delete("/cash/{cash_id}", status_code=204)
def delete_cash(cash_id: int, db: Session = Depends(get_db)):
    cf = db.get(CashFlow, cash_id)
    if not cf:
        raise HTTPException(404, "Cash flow not found")
    db.delete(cf)
    db.commit()
