"""Portfolio engine: holdings are always derived from transactions,
never stored. Valuation converts everything to the base currency."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import config
from app.models.models import CashFlow, Instrument, PriceSnapshot, Transaction
from app.schemas.schemas import HistoryPoint, HoldingOut, PortfolioSummary
from app.services import cache, market
from app.services.ledger import COST_METHODS, Position, apply_txn, cash_effect, split_factor_after
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


def _txns_by_instrument(db: Session) -> dict[int, list]:
    """All transactions in ONE query, grouped and ordered per instrument."""
    out: dict[int, list] = {}
    for t in db.query(Transaction).order_by(Transaction.date, Transaction.id).all():
        out.setdefault(t.instrument_id, []).append(t)
    return out


def compute_holdings(db: Session, method: str = config.COST_METHOD,
                     _txns: dict | None = None) -> list[dict]:
    """Aggregate transactions -> per-instrument position. Pure function of txns.

    `method` picks the cost basis: "wac" (weighted average) or "fifo".
    Realized P&L and the remaining cost basis depend on it; quantities,
    market value and cashflows (hence XIRR) do not.
    """
    if method not in COST_METHODS:
        method = "wac"
    by_inst = _txns if _txns is not None else _txns_by_instrument(db)
    holdings = []
    for inst in db.query(Instrument).order_by(Instrument.symbol).all():
        txns = by_inst.get(inst.id, [])
        pos = Position()
        realized_flows = []  # (date, amount_ccy, fx_to_hkd) per sell/dividend
        for t in txns:
            r = apply_txn(pos, t, method)
            if r is not None:
                realized_flows.append((t.date, r, t.fx_to_hkd))
        qty = pos.qty if pos.qty > 1e-9 else 0.0
        holdings.append({
            "instrument": inst,
            "quantity": round(qty, 6),
            "avg_cost": round(pos.cost / qty, 4) if qty > 0 else 0.0,
            "invested": round(pos.cost, 2) if qty > 0 else 0.0,
            "realized_pnl": round(pos.realized, 2),
            "realized_flows": realized_flows,
            "transactions": txns,
        })
    return holdings


def _latest_prices(db: Session) -> dict[int, PriceSnapshot]:
    """Latest snapshot per instrument in one query (was one query each)."""
    sub = (db.query(PriceSnapshot.instrument_id, func.max(PriceSnapshot.date).label("d"))
           .group_by(PriceSnapshot.instrument_id).subquery())
    rows = (db.query(PriceSnapshot)
            .join(sub, (PriceSnapshot.instrument_id == sub.c.instrument_id)
                  & (PriceSnapshot.date == sub.c.d)).all())
    return {r.instrument_id: r for r in rows}


def latest_price(db: Session, instrument_id: int):
    return (
        db.query(PriceSnapshot)
        .filter_by(instrument_id=instrument_id)
        .order_by(PriceSnapshot.date.desc())
        .first()
    )


def _rates_key(rates: dict) -> tuple:
    return tuple(sorted((k, round(v, 6) if v else None) for k, v in rates.items()))


def portfolio_summary(db: Session, base: str = config.BASE_CURRENCY,
                      method: str = config.COST_METHOD) -> PortfolioSummary:
    """Cached by (data_version, base, method, FX, today) — see cache.py."""
    from datetime import date as _d
    base = base.upper()
    method = method if method in COST_METHODS else "wac"
    rates = _fx_rates()
    key = ("summary", cache.data_version(db), base, method, _rates_key(rates), _d.today())
    res = cache.get_or_compute(key, lambda: _portfolio_summary(db, base, method, rates))
    return res.model_copy(deep=True)


def _portfolio_summary(db: Session, base: str, method: str, rates: dict) -> PortfolioSummary:
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

    txns_map = _txns_by_instrument(db)
    holdings = compute_holdings(db, method, _txns=txns_map)
    prices = _latest_prices(db)
    for h in holdings:
        inst = h["instrument"]
        snap = prices.get(inst.id)
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
            if t.type == "split":
                continue
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
                if t.type == "split":
                    continue
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
        for h in holdings:
            ccy = h["instrument"].currency
            for t in h["transactions"]:
                # buys leave the account; sell proceeds and dividends land in it
                bal[ccy] = bal.get(ccy, 0.0) + cash_effect(t)
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
        cost_method=method,
    )


def portfolio_history(db: Session, base: str = config.BASE_CURRENCY,
                      method: str = config.COST_METHOD) -> list[HistoryPoint]:
    """Cached by (data_version, base, method, FX) — see cache.py."""
    base = base.upper()
    method = method if method in COST_METHODS else "wac"
    rates = _fx_rates()
    key = ("history", cache.data_version(db), base, method, _rates_key(rates))
    res = cache.get_or_compute(key, lambda: _portfolio_history(db, base, method, rates))
    return [p.model_copy() for p in res]


def _portfolio_history(db: Session, base: str, method: str, rates: dict) -> list[HistoryPoint]:
    """Daily total portfolio value, cost basis and time-weighted return.

    Built ONLY from persisted rows — never triggers a live fetch:
    - quantity / cost basis per day is replayed from transactions;
    - close per day is the latest snapshot on/before that day (carry-forward);
    - FX uses today's rates for every day (documented approximation), so
      older points mix old prices with today's FX.
    - daily closes are split-adjusted, so before a recorded split the share
      count is scaled by the later split ratios when valuing it.
    Days before the first transaction are skipped; days before an
    instrument's first snapshot contribute 0 for that leg.

    `twr` is the cumulative time-weighted return (0.12 = +12%) — it strips
    out money put in / taken out, so it is comparable with an index
    benchmark. Daily step, flows assumed at the start of the day:
        r_d = (V_d + dividends_d) / (V_{d-1} + net_buys_d) - 1
    """
    insts = db.query(Instrument).all()
    if not insts:
        return []

    by_inst = _txns_by_instrument(db)
    txns = {i.id: by_inst.get(i.id, []) for i in insts}
    splits = {i.id: [(t.date, t.quantity) for t in txns[i.id] if t.type == "split"]
              for i in insts}
    snaps: dict[int, list] = {i.id: [] for i in insts}
    for sid, sd, sc in (db.query(PriceSnapshot.instrument_id, PriceSnapshot.date,
                                 PriceSnapshot.close)
                        .order_by(PriceSnapshot.date).all()):
        if sid in snaps:
            snaps[sid].append((sd, sc))
    all_t = [t for ts in txns.values() for t in ts]
    first_txn = min((t.date for t in all_t), default=None)
    days = sorted({d for ss in snaps.values() for d, _ in ss
                   if first_txn is None or d >= first_txn})
    if not days:
        return []

    # per-instrument running state, advanced day by day
    pos = {i.id: Position() for i in insts}
    st = {i.id: {"ti": 0, "si": 0, "close": None} for i in insts}
    out: list[HistoryPoint] = []
    prev_value = None
    index = 1.0
    for d in days:
        total = cost_total = 0.0
        flow = income = 0.0
        ok = True
        for i in insts:
            s_ = st[i.id]
            p_ = pos[i.id]
            tl = txns[i.id]
            while s_["ti"] < len(tl) and tl[s_["ti"]].date <= d:
                t = tl[s_["ti"]]
                s_["ti"] += 1
                apply_txn(p_, t, method)
                if t.type == "split":
                    continue
                if t.type == "dividend":  # income, not a flow
                    b = _to_base(cash_effect(t), i.currency, base, rates)
                    if b is None:
                        ok = False
                    else:
                        income += b
                    continue
                # net money put into positions: buys +, sell proceeds -
                b = _to_base(-cash_effect(t), i.currency, base, rates)
                if b is None:
                    ok = False
                else:
                    flow += b
            sl = snaps[i.id]
            while s_["si"] < len(sl) and sl[s_["si"]][0] <= d:
                s_["close"] = sl[s_["si"]][1]
                s_["si"] += 1
            if p_.qty <= 1e-9:
                continue
            c = _to_base(p_.cost, i.currency, base, rates)
            if c is None:
                ok = False
            else:
                cost_total += c
            if s_["close"] is None:
                continue  # no price yet on this day -> contributes 0
            qty_adj = p_.qty * split_factor_after(splits[i.id], d) if splits[i.id] else p_.qty
            leg = _to_base(qty_adj * s_["close"], i.currency, base, rates)
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
