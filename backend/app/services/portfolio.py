"""Portfolio engine: holdings are always derived from transactions,
never stored. Valuation converts everything to the base currency."""
from sqlalchemy.orm import Session

from app import config
from app.models.models import CashFlow, Instrument, PriceSnapshot, Transaction
from app.schemas.schemas import HistoryPoint, HoldingOut, PortfolioSummary
from app.services import market
from app.services.xirr import xirr

# to-HKD rates; extend as needed
TO_HKD = {"HKD": 1.0, "USD": None, "CNY": None}  # USD/CNY filled at runtime


def _fx_rates() -> dict[str, float | None]:
    # FX goes through the active market-data provider (cached, 10-min TTL).
    # Callers must never import yfinance directly — see market.py.
    return {
        "HKD": 1.0,
        "USD": market.fetch_fx_to_hkd("USD"),
        "CNY": market.fetch_fx_to_hkd("CNY"),
    }


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
        cost = 0.0  # cash spent to acquire the current position (average-cost)
        realized = 0.0  # cumulative realized P&L in instrument currency
        realized_flows = []  # (date, amount_ccy, fx_to_hkd) per sell/dividend
        for t in txns:
            if t.type == "buy":
                qty += t.quantity
                cost += t.quantity * t.price + t.fee
            elif t.type == "sell":
                if qty > 0:
                    # average-cost: selling removes its proportional share of cost.
                    # sell fees are an expense on proceeds (handled in cashflows),
                    # they must NOT reduce cost basis — otherwise selling everything
                    # leaves cost at -fee instead of 0.
                    # realized = proceeds - cost of shares sold - fee
                    avg = cost / qty
                    sq = min(t.quantity, qty)
                    r = sq * t.price - sq * avg - t.fee
                    realized += r
                    realized_flows.append((t.date, r, t.fx_to_hkd))
                    cost -= sq * avg
                qty -= t.quantity
                if qty <= 0:
                    qty, cost = 0.0, 0.0
            elif t.type == "dividend":
                # cash received, net of any withholding tax in fee
                r = t.quantity * t.price - t.fee
                realized += r
                realized_flows.append((t.date, r, t.fx_to_hkd))
        holdings.append({
            "instrument": inst,
            "quantity": round(qty, 6),
            "avg_cost": round(cost / qty, 4) if qty > 0 else 0.0,
            "invested": round(cost, 2),
            "realized_pnl": round(realized, 2),
            "realized_flows": realized_flows,
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
    fx_gaps: set[str] = set()  # currencies we couldn't convert (FX fetch failed)
    total_value = 0.0
    total_invested = 0.0
    realized_base = 0.0
    dividends_12m = 0.0
    has_price = False
    latest_price_date = None
    quotes_as_of = None
    quotes_source = None

    # cashflows for XIRR: (date, amount in base currency); buys negative
    cashflows: list[tuple] = []

    from datetime import date as date_cls
    from datetime import timedelta
    div_cutoff = date_cls.today() - timedelta(days=365)

    for h in compute_holdings(db):
        inst = h["instrument"]
        snap = latest_price(db, inst.id)
        invested_base = _to_base(h["invested"], inst.currency, base, rates)
        if invested_base is None:
            fx_gaps.add(inst.currency)
        else:
            total_invested += invested_base

        mv = pnl = mv_base = pnl_base = None
        price_date = None
        prev_close = day_chg = day_chg_pct = day_chg_base = None
        if snap:
            has_price = True
            price_date = snap.date
            if snap.fetched_at and (quotes_as_of is None or snap.fetched_at > quotes_as_of):
                quotes_as_of = snap.fetched_at
                quotes_source = snap.source
            if latest_price_date is None or price_date > latest_price_date:
                latest_price_date = price_date
            mv = h["quantity"] * snap.close
            pnl = mv - h["invested"]
            mv_base = _to_base(mv, inst.currency, base, rates)
            pnl_base = _to_base(pnl, inst.currency, base, rates)
            if mv_base is None or pnl_base is None:
                fx_gaps.add(inst.currency)
            else:
                total_value += mv_base
            prev_close = snap.prev_close
            if prev_close:
                day_chg = snap.close - prev_close
                day_chg_pct = day_chg / prev_close if prev_close else None
                day_chg_base = _to_base(day_chg * h["quantity"], inst.currency, base, rates)
                if day_chg_base is None:
                    fx_gaps.add(inst.currency)
        else:
            stale.append(inst.symbol)

        # cashflows from transactions.
        # XIRR signs: buys are outflows (cost + fee), sells/dividends are
        # inflows NET of fee (fee on sell, withholding tax on dividends) —
        # adding the fee would count it as profit.
        # Amounts convert at the FX rate captured on the transaction date
        # (t.fx_to_hkd), falling back to the current rate for old rows.
        for t in h["transactions"]:
            eff_rates = dict(rates)
            if t.fx_to_hkd:
                eff_rates[inst.currency] = t.fx_to_hkd
            amt_base = _to_base(t.quantity * t.price, inst.currency, base, eff_rates)
            fee_base = _to_base(t.fee, inst.currency, base, eff_rates)
            if amt_base is None or fee_base is None:
                continue
            if t.type == "buy":
                cashflows.append((t.date, -(amt_base + fee_base)))
            elif t.type == "sell":
                cashflows.append((t.date, amt_base - fee_base))
            elif t.type == "dividend":
                cashflows.append((t.date, amt_base - fee_base))
                if t.date >= div_cutoff:
                    dividends_12m += amt_base - fee_base

        holdings_out.append(HoldingOut(
            instrument_id=inst.id, symbol=inst.symbol, name=inst.name,
            market=inst.market, currency=inst.currency,
            quantity=h["quantity"], avg_cost=h["avg_cost"], invested=h["invested"],
            realized_pnl=h["realized_pnl"],
            latest_price=snap.close if snap else None, price_date=price_date,
            market_value=round(mv, 2) if mv is not None else None,
            unrealized_pnl=round(pnl, 2) if pnl is not None else None,
            market_value_base=round(mv_base, 2) if mv_base is not None else None,
            unrealized_pnl_base=round(pnl_base, 2) if pnl_base is not None else None,
            prev_close=round(prev_close, 4) if prev_close else None,
            day_change=round(day_chg, 4) if day_chg is not None else None,
            day_change_pct=round(day_chg_pct, 4) if day_chg_pct is not None else None,
            day_change_base=round(day_chg_base, 2) if day_chg_base is not None else None,
        ))

        # realized P&L converted at each event's transaction-date FX
        for (d_, amt_ccy, fx) in h["realized_flows"]:
            eff = dict(rates)
            if fx:
                eff[inst.currency] = fx
            b = _to_base(amt_ccy, inst.currency, base, eff)
            if b is None:
                fx_gaps.add(inst.currency)
            else:
                realized_base += b

    # cash in/out of the account: deposits are investor outflows (negative),
    # withdrawals are inflows (positive). Converted at today's FX — cash legs
    # don't store historical FX (documented approximation).
    for cf in db.query(CashFlow).order_by(CashFlow.date).all():
        amt_base = _to_base(cf.amount, cf.currency, base, rates)
        if amt_base is None:
            fx_gaps.add(cf.currency)
            continue
        cashflows.append((cf.date, -amt_base if cf.direction == "in" else amt_base))

    # second pass: weight of each holding (needs the final total_value)
    if total_value > 0:
        for ho in holdings_out:
            if ho.market_value_base:
                ho.weight_pct = round(ho.market_value_base / total_value * 100, 1)

    # terminal value for XIRR — dated at the latest price date, NOT today:
    # annualizing over (today - first_cashflow) when prices are days old
    # inflates the rate. Only computed when every holding has a fresh price,
    # otherwise the IRR would be built on a partial terminal value.
    xirr_value = None
    # totals are only trustworthy with full prices AND full FX coverage;
    # a partial total is worse than no total.
    # total_pnl is the TRUE cumulative P&L: unrealized (value - remaining
    # cost) + realized (sells & dividends, net of fees).
    complete = not stale and not fx_gaps
    unrealized_base = total_value - total_invested
    if has_price and total_value > 0:
        cashflows.append((latest_price_date or date_cls.today(), total_value))
    if len(cashflows) >= 2 and complete:
        r = xirr(cashflows)
        xirr_value = round(r, 4) if r is not None else None

    return PortfolioSummary(
        base_currency=base,
        fx_usd_to_base=rates.get("USD") if base == "HKD" else None,
        total_value=round(total_value, 2) if complete else None,
        total_invested=round(total_invested, 2) if not fx_gaps else None,
        total_pnl=round(unrealized_base + realized_base, 2) if complete else None,
        unrealized_pnl=round(unrealized_base, 2) if complete else None,
        realized_pnl=round(realized_base, 2) if not fx_gaps else None,
        xirr=xirr_value,
        holdings=holdings_out,
        price_stale=stale,
        fx_stale=sorted(fx_gaps),
        quotes_as_of=quotes_as_of,
        quotes_source=quotes_source,
        dividends_12m=round(dividends_12m, 2) if not fx_gaps else None,
    )


def portfolio_history(db: Session, base: str = config.BASE_CURRENCY) -> list[HistoryPoint]:
    """Daily total portfolio value in `base` currency.

    Built ONLY from persisted rows — never triggers a live fetch:
    - quantity per day is reconstructed from transactions (buy/sell change it,
      dividends don't);
    - close per day is the latest snapshot on/before that day (carry-forward);
    - FX uses today's rates for every day (documented approximation — we don't
      store historical FX), so older points mix old prices with today's FX.
    Days before an instrument's first snapshot contribute 0 for that leg.
    """
    base = base.upper()
    insts = db.query(Instrument).all()
    if not insts:
        return []

    rates = _fx_rates()

    # per-instrument timelines
    txns = {i.id: sorted(db.query(Transaction).filter_by(instrument_id=i.id).all(),
                         key=lambda t: (t.date, t.id)) for i in insts}
    snaps = {i.id: sorted(db.query(PriceSnapshot).filter_by(instrument_id=i.id).all(),
                          key=lambda s: s.date) for i in insts}
    days = sorted({s.date for ss in snaps.values() for s in ss})
    if not days:
        return []

    out: list[HistoryPoint] = []
    for d in days:
        total = 0.0
        ok = True
        for i in insts:
            qty = 0.0
            for t in txns[i.id]:
                if t.date > d:
                    break
                if t.type == "buy":
                    qty += t.quantity
                elif t.type == "sell":
                    qty -= t.quantity
            if qty <= 0:
                continue
            close = None
            for s in snaps[i.id]:
                if s.date > d:
                    break
                close = s.close
            if close is None:
                continue  # no price yet on this day -> contributes 0
            leg = _to_base(qty * close, i.currency, base, rates)
            if leg is None:
                ok = False
                break
            total += leg
        out.append(HistoryPoint(date=d, value=round(total, 2) if ok else None))
    return out
