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
    day_pnl_total = 0.0
    day_pnl_n = 0

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

        # per-holding XIRR: this position's own cashflows + its market value
        h_xirr = None
        if mv_base is not None and snap:
            h_flows = []
            for t in h["transactions"]:
                eff = dict(rates)
                if t.fx_to_hkd:
                    eff[inst.currency] = t.fx_to_hkd
                a_ = _to_base(t.quantity * t.price, inst.currency, base, eff)
                f_ = _to_base(t.fee, inst.currency, base, eff)
                if a_ is None or f_ is None:
                    h_flows = []
                    break
                h_flows.append((t.date, -(a_ + f_) if t.type == "buy" else a_ - f_))
            if h_flows and mv_base > 0:
                h_flows.append((snap.date, mv_base))
            if len(h_flows) >= 2:
                r_ = xirr(h_flows)
                h_xirr = round(r_, 4) if r_ is not None else None
        if day_chg_base is not None:
            day_pnl_total += day_chg_base
            day_pnl_n += 1

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
            unrealized_pnl_pct=round(pnl / h["invested"], 4)
            if pnl is not None and h["invested"] > 0 else None,
            xirr=h_xirr,
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

    # ---- XIRR perspective ----
    # Without recorded cash movements, XIRR is computed on the trades
    # themselves (buys out, sells/dividends in, positions as terminal value).
    # Once deposits/withdrawals are recorded, the perspective switches to the
    # ACCOUNT: only money crossing the account boundary is a cashflow
    # (deposit = outflow, withdrawal = inflow), and the terminal value is
    # positions + idle cash. Mixing both (v0.1) counted every dollar twice —
    # once when deposited and again when it bought something — which dragged
    # XIRR far below the real return.
    cash_rows = db.query(CashFlow).order_by(CashFlow.date).all()
    cash_balance_base = None
    if cash_rows:
        bal: dict[str, float] = {}
        for cf in cash_rows:
            bal[cf.currency] = bal.get(cf.currency, 0.0) + (cf.amount if cf.direction == "in" else -cf.amount)
        for h in compute_holdings(db):
            ccy = h["instrument"].currency
            for t in h["transactions"]:
                gross = t.quantity * t.price
                if t.type == "buy":
                    bal[ccy] = bal.get(ccy, 0.0) - gross - t.fee
                else:  # sell proceeds and dividends land in the account
                    bal[ccy] = bal.get(ccy, 0.0) + gross - t.fee
        cash_balance_base = 0.0
        for ccy, amt in bal.items():
            b = _to_base(amt, ccy, base, rates)
            if b is None:
                fx_gaps.add(ccy)
                cash_balance_base = None
                break
            cash_balance_base += b
        cashflows = []
        for cf in cash_rows:
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
    terminal = total_value + (cash_balance_base or 0.0)
    if has_price and terminal > 0:
        cashflows.append((latest_price_date or date_cls.today(), terminal))
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
        day_pnl=round(day_pnl_total, 2) if complete and day_pnl_n else None,
        cash_balance=round(cash_balance_base, 2) if cash_balance_base is not None and complete else None,
        day_pnl_pct=round(day_pnl_total / (total_value - day_pnl_total), 4)
        if complete and day_pnl_n and total_value - day_pnl_total > 0 else None,
    )


def portfolio_history(db: Session, base: str = config.BASE_CURRENCY) -> list[HistoryPoint]:
    """Daily total portfolio value, cost basis and time-weighted return.

    Built ONLY from persisted rows — never triggers a live fetch:
    - quantity / average-cost basis per day is replayed from transactions;
    - close per day is the latest snapshot on/before that day (carry-forward);
    - FX uses today's rates for every day (documented approximation), so
      older points mix old prices with today's FX.
    Days before the first transaction are skipped; days before an
    instrument's first snapshot contribute 0 for that leg.

    `twr` is the cumulative time-weighted return (0.12 = +12%) — it strips
    out money put in / taken out, so it is comparable with an index
    benchmark. Daily step, flows assumed at the start of the day:
        r_d = (V_d + dividends_d) / (V_{d-1} + net_buys_d) - 1
    """
    base = base.upper()
    insts = db.query(Instrument).all()
    if not insts:
        return []

    rates = _fx_rates()
    txns = {i.id: sorted(db.query(Transaction).filter_by(instrument_id=i.id).all(),
                         key=lambda t: (t.date, t.id)) for i in insts}
    snaps = {i.id: sorted(db.query(PriceSnapshot).filter_by(instrument_id=i.id).all(),
                          key=lambda s: s.date) for i in insts}
    all_t = [t for ts in txns.values() for t in ts]
    first_txn = min((t.date for t in all_t), default=None)
    days = sorted({s.date for ss in snaps.values() for s in ss
                   if first_txn is None or s.date >= first_txn})
    if not days:
        return []

    # per-instrument running state, advanced day by day
    st = {i.id: {"qty": 0.0, "cost": 0.0, "ti": 0, "si": 0, "close": None} for i in insts}
    out: list[HistoryPoint] = []
    prev_value = None
    index = 1.0
    for d in days:
        total = cost_total = 0.0
        flow = income = 0.0
        ok = True
        for i in insts:
            s_ = st[i.id]
            tl = txns[i.id]
            while s_["ti"] < len(tl) and tl[s_["ti"]].date <= d:
                t = tl[s_["ti"]]
                s_["ti"] += 1
                gross = t.quantity * t.price
                if t.type == "buy":
                    s_["qty"] += t.quantity
                    s_["cost"] += gross + t.fee
                    leg = gross + t.fee
                elif t.type == "sell":
                    if s_["qty"] > 0:
                        avg = s_["cost"] / s_["qty"]
                        s_["cost"] -= min(t.quantity, s_["qty"]) * avg
                    s_["qty"] -= t.quantity
                    if s_["qty"] <= 1e-12:
                        s_["qty"], s_["cost"] = 0.0, 0.0
                    leg = -(gross - t.fee)
                else:  # dividend: income, not a flow
                    b = _to_base(gross - t.fee, i.currency, base, rates)
                    if b is None:
                        ok = False
                    else:
                        income += b
                    continue
                b = _to_base(leg, i.currency, base, rates)
                if b is None:
                    ok = False
                else:
                    flow += b
            sl = snaps[i.id]
            while s_["si"] < len(sl) and sl[s_["si"]].date <= d:
                s_["close"] = sl[s_["si"]].close
                s_["si"] += 1
            if s_["qty"] <= 0:
                continue
            c = _to_base(s_["cost"], i.currency, base, rates)
            if c is None:
                ok = False
            else:
                cost_total += c
            if s_["close"] is None:
                continue  # no price yet on this day -> contributes 0
            leg = _to_base(s_["qty"] * s_["close"], i.currency, base, rates)
            if leg is None:
                ok = False
                continue
            total += leg
        if not ok:
            out.append(HistoryPoint(date=d, value=None))
            continue
        denom = (prev_value or 0.0) + flow
        if denom > 0:
            index *= (total + income) / denom
        prev_value = total
        out.append(HistoryPoint(date=d, value=round(total, 2),
                                cost=round(cost_total, 2),
                                twr=round(index - 1.0, 6)))
    return out
