"""Market data via yfinance. Symbols are stored as Yahoo tickers already
(e.g. "SGOV" for US, "03152.HK" for Hong Kong), so no translation layer.

yfinance is an optional dependency: if it is not installed, every fetch
returns None and the API reports the symbols as failed instead of crashing.
"""
from datetime import date

from sqlalchemy.orm import Session

from app import config
from app.models.models import Instrument, PriceSnapshot

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None


def fetch_close(symbol: str) -> tuple[date, float] | None:
    """Latest daily close for a Yahoo ticker. Returns None on any failure."""
    if yf is None:
        return None
    try:
        hist = yf.Ticker(symbol).history(period="5d", timeout=config.YFINANCE_TIMEOUT)
        if hist is None or hist.empty:
            return None
        last = hist.iloc[-1]
        d = hist.index[-1].date()
        return d, float(last["Close"])
    except Exception:
        return None


def fetch_usd_to_hkd() -> float | None:
    """HKD per 1 USD, via the HKD=X forex ticker."""
    res = fetch_close("HKD=X")
    return res[1] if res else None


def refresh_all(db: Session) -> dict:
    """Pull latest closes for every instrument, upsert snapshots."""
    instruments = db.query(Instrument).all()
    updated, failed = [], []
    for inst in instruments:
        res = fetch_close(inst.symbol)
        if res is None:
            failed.append(inst.symbol)
            continue
        d, close = res
        snap = (
            db.query(PriceSnapshot)
            .filter_by(instrument_id=inst.id, date=d)
            .one_or_none()
        )
        if snap:
            snap.close = close
        else:
            db.add(PriceSnapshot(instrument_id=inst.id, date=d, close=close))
        updated.append(inst.symbol)
    db.commit()
    return {"updated": updated, "failed": failed}
