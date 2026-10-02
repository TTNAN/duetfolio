"""Portfolio engine: holdings are always derived from transactions,
never stored. Valuation converts everything to the base currency."""
from sqlalchemy.orm import Session

from app import config
from app.models.models import Instrument, PriceSnapshot, Transaction
from app.schemas.schemas import HoldingOut, PortfolioSummary
from app.services.market import fetch_usd_to_hkd
from app.services.xirr import xirr

# to-HKD rates; extend as needed
TO_HKD = {"HKD": 1.0, "USD": None, "CNY": None}  # USD/CNY filled at runtime


def _fx_rates() -> dict[str, float | None]:
    rates = dict(TO_HKD)
    usd_hkd = fetch_usd_to_hkd()
    rates["USD"] = usd_hkd
    # CNY via USD: USD/CNY ticker, then HKD = USD_HKD / USD_CNY
    if usd_hkd:
        try:
            import yfinance as yf
            hist = yf.Ticker("CNY=X").history(period="5d", timeout=config.YFINANCE_TIMEOUT)
            if hist is not None and not hist.empty:
                usd_cny = float(hist.iloc[-1]["Close"])
                rates["CNY"] = usd_hkd / usd_cny if usd_cny else None
        except Exception:
            pass
    return rates


def _to_base(amount: float, currency: str, base: str, rates: dict) -> float | None:
    """Convert amount in `currency` to base currency via HKD pivot."""
    if base == currency:
        return amount
    pivot = rates.get(currency)
    base_pivot = rates.get(base)
    if pivot is None or base_pivot is None:
        return None
    return amount * pivot / base_pivot


def compute_holdings(db: Session) -> list[dict]:
    """Aggregate transactions -> per-instrument position. Pure function of txns."""
    holdings = []
    for inst in db.query(Instrument).order_by(Instrument.symbol).all():
        txns = (
            db.query(Transaction)
            .filter_by(instrument_id=inst.id)
            .order_by(Transaction.date, Transaction.id)
            .all()
        )
        qty = 0.0
        cost = 0.0  # total cash spent incl. fees
        for t in txns:
            if t.type == "buy":
                qty += t.quantity
                cost += t.quantity * t.price + t.fee
            elif t.type == "sell":
                if qty > 0:
                    # reduce cost basis proportionally (average-cost method)
                    cost -= cost * (t.quantity / qty)
                qty -= t.quantity
                cost -= t.fee  # fees on sell reduce net proceeds, tracked in cashflows
        holdings.append({
            "instrument": inst,
            "quantity": round(qty, 6),
            "avg_cost": round(cost / qty, 4) if qty > 0 else 0.0,
            "invested": round(cost, 2),
            "transactions": txns,
        })
    return holdings


def latest_price(db: Session, instrument_id: int):
    return (
        db.query(PriceSnapshot)
        .filter_by(instrument_id=instrument_id)
        .order_by(PriceSnapshot.date.desc())
        .first()
    )


def portfolio_summary(db: Session, base: str = config.BASE_CURRENCY) -> PortfolioSummary:
    base = base.upper()
    rates = _fx_rates()
    holdings_out: list[HoldingOut] = []
    stale: list[str] = []
    total_value = 0.0
    total_invested = 0.0
    has_price = False

    # cashflows for XIRR: (date, amount in base currency); buys negative
    cashflows: list[tuple] = []

    for h in compute_holdings(db):
        inst = h["instrument"]
        snap = latest_price(db, inst.id)
        invested_base = _to_base(h["invested"], inst.currency, base, rates)
        if invested_base is not None:
            total_invested += invested_base

        mv = pnl = mv_base = pnl_base = None
        price_date = None
        if snap:
            has_price = True
            price_date = snap.date
            mv = h["quantity"] * snap.close
            pnl = mv - h["invested"]
            mv_base = _to_base(mv, inst.currency, base, rates)
            pnl_base = _to_base(pnl, inst.currency, base, rates)
            if mv_base is not None:
                total_value += mv_base
        else:
            stale.append(inst.symbol)

        # cashflows from transactions
        for t in h["transactions"]:
            amt = t.quantity * t.price + t.fee
            amt_base = _to_base(amt, inst.currency, base, rates)
            if amt_base is None:
                continue
            if t.type == "buy":
                cashflows.append((t.date, -amt_base))
            elif t.type == "sell":
                cashflows.append((t.date, amt_base - _to_base(t.fee, inst.currency, base, rates)))
            elif t.type == "dividend":
                cashflows.append((t.date, amt_base))

        holdings_out.append(HoldingOut(
            instrument_id=inst.id, symbol=inst.symbol, name=inst.name,
            market=inst.market, currency=inst.currency,
            quantity=h["quantity"], avg_cost=h["avg_cost"], invested=h["invested"],
            latest_price=snap.close if snap else None, price_date=price_date,
            market_value=round(mv, 2) if mv is not None else None,
            unrealized_pnl=round(pnl, 2) if pnl is not None else None,
            market_value_base=round(mv_base, 2) if mv_base is not None else None,
            unrealized_pnl_base=round(pnl_base, 2) if pnl_base is not None else None,
        ))

    # terminal value for XIRR — only when every holding has a fresh price,
    # otherwise the IRR would be computed on a partial terminal value
    from datetime import date as date_cls
    xirr_value = None
    if has_price and total_value > 0:
        cashflows.append((date_cls.today(), total_value))
    if len(cashflows) >= 2 and not stale:
        r = xirr(cashflows)
        xirr_value = round(r, 4) if r is not None else None

    return PortfolioSummary(
        base_currency=base,
        fx_usd_to_base=rates.get("USD") if base == "HKD" else None,
        total_value=round(total_value, 2) if has_price else None,
        total_invested=round(total_invested, 2),
        total_pnl=round(total_value - total_invested, 2) if has_price else None,
        xirr=xirr_value,
        holdings=holdings_out,
        price_stale=stale,
    )
