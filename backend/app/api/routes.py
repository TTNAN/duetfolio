"""REST API: instruments, transactions, portfolio, price refresh."""
from datetime import date as date_cls

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models.models import CashFlow, Instrument, PriceSnapshot, Transaction
from app.schemas.schemas import (
    BenchmarkOut, BenchmarkPoint, CashFlowCreate, CashFlowOut, HistoryPoint,
    HoldingOut, InstrumentCandidate, InstrumentCreate, InstrumentOut,
    InstrumentUpdate, PortfolioSummary, TransactionCreate, TransactionOut,
    TransactionUpdate,
)
from app.services import market
from app.services.csvimport import parse_csv
from app.services.portfolio import compute_holdings, latest_price, portfolio_history, portfolio_summary

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "version": "0.3.0", "base_currency": config.BASE_CURRENCY,
            "market_provider": config.MARKET_PROVIDER, "demo": config.DEMO_MODE,
            "cost_method": config.COST_METHOD}


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


@router.patch("/instruments/{instrument_id}", response_model=InstrumentOut)
def update_instrument(instrument_id: int, body: InstrumentUpdate,
                      db: Session = Depends(get_db)):
    inst = db.get(Instrument, instrument_id)
    if not inst:
        raise HTTPException(404, "Instrument not found")
    for field in ("name", "asset_type"):
        v = getattr(body, field)
        if v is not None:
            setattr(inst, field, v)
    db.commit()
    db.refresh(inst)
    return inst


@router.get("/instruments/{instrument_id}/prices")
def instrument_prices(instrument_id: int, db: Session = Depends(get_db)):
    """Stored daily closes for one instrument (for the holding drawer chart)."""
    if not db.get(Instrument, instrument_id):
        raise HTTPException(404, "Instrument not found")
    rows = (db.query(PriceSnapshot.date, PriceSnapshot.close)
            .filter_by(instrument_id=instrument_id)
            .order_by(PriceSnapshot.date).all())
    return [{"date": d_.isoformat(), "close": c} for d_, c in rows]


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


def _first_oversell(db: Session, instrument_id: int) -> float | None:
    """Replay one instrument; return the negative quantity a sell would
    leave (accounting for splits), or None when the ledger is consistent."""
    qty = 0.0
    for t in (db.query(Transaction).filter_by(instrument_id=instrument_id)
              .order_by(Transaction.date, Transaction.id).all()):
        if t.type == "buy":
            qty += t.quantity
        elif t.type == "sell":
            qty -= t.quantity
            if qty < -1e-6:
                return qty
        elif t.type == "split":
            qty *= t.quantity
    return None


def _after_split_change(db: Session, inst: Instrument) -> None:
    """Daily history must be split-adjusted for the valuation to be right.
    Snapshots stored before we knew about the split may be unadjusted, so
    drop that instrument's daily closes and re-fetch adjusted history
    (best effort — the latest live quote is kept)."""
    latest = (db.query(PriceSnapshot).filter_by(instrument_id=inst.id)
              .order_by(PriceSnapshot.date.desc()).first())
    q = db.query(PriceSnapshot).filter(PriceSnapshot.instrument_id == inst.id)
    if latest is not None:
        q = q.filter(PriceSnapshot.id != latest.id)
    q.delete(synchronize_session=False)
    db.flush()
    try:
        market.backfill_history(db, only=[inst.id], commit=False)
    except Exception:
        pass  # offline: the user can run "backfill history" later


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
    data = body.model_dump()
    if body.type == "split":  # a ratio, not a trade: no price, fee or cash
        data.update(price=0.0, fee=0.0)
    t = Transaction(**data, fx_to_hkd=fx_to_hkd)
    db.add(t)
    if body.type == "split":
        db.flush()
        _after_split_change(db, inst)
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
    was_split = t.type == "split"
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
    # oversell guard: the edit must not make any sell exceed the shares held
    # at that point in time (replayed, so splits are accounted for)
    bad = _first_oversell(db, t.instrument_id)
    if bad is not None:
        db.rollback()
        raise HTTPException(400, f"Oversell: edit would leave {inst.symbol} at {bad:g}")
    if was_split or t.type == "split":
        _after_split_change(db, inst)
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
    inst = db.get(Instrument, t.instrument_id)
    was_split = t.type == "split"
    db.delete(t)
    db.flush()
    bad = _first_oversell(db, inst.id)
    if bad is not None:
        db.rollback()
        raise HTTPException(400, f"Oversell: deleting it would leave {inst.symbol} at {bad:g}")
    if was_split:
        _after_split_change(db, inst)
    db.commit()


@router.get("/transactions/export.csv")
def export_transactions_csv(db: Session = Depends(get_db)):
    """All transactions as CSV (re-importable through the generic importer)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "symbol", "name", "market", "currency", "side",
                "quantity", "price", "fee", "fx_to_hkd", "note"])
    rows = (db.query(Transaction, Instrument)
            .join(Instrument, Transaction.instrument_id == Instrument.id)
            .order_by(Transaction.date, Transaction.id).all())
    for t, i in rows:
        w.writerow([t.date.isoformat(), i.symbol, i.name, i.market, i.currency,
                    t.type, t.quantity, t.price, t.fee,
                    t.fx_to_hkd if t.fx_to_hkd is not None else "", t.note or ""])
    return Response(
        content="\ufeff" + buf.getvalue(),  # BOM so Excel opens UTF-8 correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="duetfolio-transactions.csv"'},
    )


# ---- broker CSV import ----
@router.post("/transactions/import/preview")
async def import_preview(file: UploadFile = File(...),
                         broker: str = Query(default="auto",
                                             pattern="^(auto|futu|tiger|ibkr|schwab|generic)$")):
    """Parse a broker CSV (Futu / Tiger / IBKR / Schwab / generic) -> preview.

    Nothing is written. The frontend shows the preview and posts back
    {"rows": [...]} to /transactions/import for the confirmed rows.
    """
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5MB)")
    return parse_csv(raw, broker=broker)


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
    method: str = Query(default=config.COST_METHOD, pattern="^(wac|fifo)$"),
    db: Session = Depends(get_db),
):
    return portfolio_summary(db, base=base, method=method)


@router.get("/portfolio/history", response_model=list[HistoryPoint])
def get_history(
    base: str = Query(default=config.BASE_CURRENCY, pattern="^(HKD|USD|CNY)$"),
    method: str = Query(default=config.COST_METHOD, pattern="^(wac|fifo)$"),
    db: Session = Depends(get_db),
):
    return portfolio_history(db, base=base, method=method)


@router.get("/portfolio/holdings", response_model=list[HoldingOut])
def get_holdings(
    base: str = Query(default=config.BASE_CURRENCY, pattern="^(HKD|USD|CNY)$"),
    method: str = Query(default=config.COST_METHOD, pattern="^(wac|fifo)$"),
    db: Session = Depends(get_db),
):
    return portfolio_summary(db, base=base, method=method).holdings


# ---- market data ----
@router.post("/prices/refresh")
def refresh_prices(force: bool = Query(default=False), db: Session = Depends(get_db)):
    """Pull latest quotes for all instruments (concurrently). Quotes younger
    than QUOTE_TTL_SECONDS are kept unless force=true."""
    return market.refresh_all(db, force=force)


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


@router.post("/prices/backfill")
def backfill_prices(db: Session = Depends(get_db)):
    """Fill daily closes since each instrument's first trade (missing days only)."""
    return market.backfill_history(db)


@router.get("/benchmark", response_model=BenchmarkOut)
def get_benchmark(
    symbol: str = Query(..., max_length=16),
    start: date_cls = Query(...),
):
    """Daily closes of an index ETF, for the return-vs-benchmark chart.
    Returns an empty list (not an error) when every source is unreachable."""
    if symbol not in market.BENCHMARKS:
        raise HTTPException(400, f"Unsupported benchmark {symbol}")
    rows, src = market.benchmark_series(symbol, start)
    return BenchmarkOut(symbol=symbol, name=market.BENCHMARKS[symbol], source=src,
                        points=[BenchmarkPoint(date=d, close=round(c, 4)) for d, c in rows])


@router.get("/benchmarks")
def list_benchmarks():
    return [{"symbol": k, "name": v} for k, v in market.BENCHMARKS.items()]


# ---- full backup / restore ----
BACKUP_VERSION = 1


@router.get("/backup")
def export_backup(db: Session = Depends(get_db)):
    """Everything needed to rebuild the ledger, as one JSON file.
    Price snapshots are a cache and are left out (refresh/backfill rebuilds them)."""
    insts = db.query(Instrument).order_by(Instrument.id).all()
    payload = {
        "app": "duetfolio",
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "instruments": [
            {"symbol": i.symbol, "name": i.name, "market": i.market,
             "currency": i.currency, "asset_type": i.asset_type}
            for i in insts],
        "transactions": [
            {"symbol": i.symbol, "type": t.type, "quantity": t.quantity,
             "price": t.price, "fee": t.fee, "date": t.date.isoformat(),
             "note": t.note or "", "fx_to_hkd": t.fx_to_hkd}
            for i in insts for t in sorted(i.transactions, key=lambda x: (x.date, x.id))],
        "cash_flows": [
            {"date": c.date.isoformat(), "direction": c.direction,
             "amount": c.amount, "currency": c.currency, "note": c.note or ""}
            for c in db.query(CashFlow).order_by(CashFlow.date, CashFlow.id).all()],
    }
    import json
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="duetfolio-backup-{stamp}.json"'},
    )


@router.post("/backup/restore")
async def restore_backup(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Replace the whole ledger with a backup file. Validates before deleting."""
    import json
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
        assert data.get("app") == "duetfolio"
        insts = data["instruments"]
        txns = data["transactions"]
        cash = data.get("cash_flows") or []
        syms = {i["symbol"] for i in insts}
        for t in txns:
            assert t["symbol"] in syms and t["type"] in ("buy", "sell", "dividend", "split")
            date_cls.fromisoformat(t["date"])
            float(t["quantity"]), float(t["price"])
    except Exception:
        raise HTTPException(400, "Not a valid duetfolio backup file")
    db.query(PriceSnapshot).delete()
    db.query(Transaction).delete()
    db.query(Instrument).delete()
    db.query(CashFlow).delete()
    db.flush()
    by_sym = {}
    for i in insts:
        obj = Instrument(symbol=i["symbol"], name=i.get("name") or i["symbol"],
                         market=i.get("market", "US"), currency=i.get("currency", "USD"),
                         asset_type=i.get("asset_type", "stock"))
        db.add(obj)
        by_sym[i["symbol"]] = obj
    db.flush()
    for t in txns:
        db.add(Transaction(instrument_id=by_sym[t["symbol"]].id, type=t["type"],
                           quantity=float(t["quantity"]), price=float(t["price"]),
                           fee=float(t.get("fee") or 0), date=date_cls.fromisoformat(t["date"]),
                           note=t.get("note") or "", fx_to_hkd=t.get("fx_to_hkd")))
    for c in cash:
        db.add(CashFlow(date=date_cls.fromisoformat(c["date"]), direction=c["direction"],
                        amount=float(c["amount"]), currency=c.get("currency", "HKD"),
                        note=c.get("note") or ""))
    db.commit()
    return {"instruments": len(insts), "transactions": len(txns), "cash_flows": len(cash)}
