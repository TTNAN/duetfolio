"""Market data providers.

Architecture: every provider implements BaseProvider. The active provider is
chosen by the MARKET_PROVIDER env var ("yfinance" default, "eastmoney"
optional). Callers (refresh_all, portfolio engine) never touch a provider
directly — they use the module-level fetch_close / fetch_usd_to_hkd /
fetch_fx_to_hkd, which delegate to the active provider.

- yfinance: official-ish, zero-setup, ~15min delayed quotes.
- eastmoney: unofficial push2.eastmoney.com API. Closer to real-time for
  CN-based investors and needs no API key, but it is undocumented and may
  break without notice. Any failure degrades to None (reported as "failed").
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date

from sqlalchemy.orm import Session

from app import config
from app.models.models import Instrument, PriceSnapshot

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

HTTP_TIMEOUT = 15
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _http_get_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None


class BaseProvider:
    name = "base"

    def fetch_close(self, symbol: str) -> tuple[date, float] | None:
        """Latest close for a Yahoo-format ticker (e.g. "SGOV", "3152.HK")."""
        raise NotImplementedError

    def fetch_usd_to_hkd(self) -> float | None:
        """HKD per 1 USD."""
        raise NotImplementedError

    def fetch_fx_to_hkd(self, currency: str, d: date | None = None) -> float | None:
        """HKD per 1 unit of `currency`; on date d, or latest when d is None."""
        raise NotImplementedError


class YFinanceProvider(BaseProvider):
    name = "yfinance"

    def fetch_close(self, symbol: str) -> tuple[date, float] | None:
        if yf is None:
            return None
        try:
            hist = yf.Ticker(symbol).history(period="5d", timeout=config.YFINANCE_TIMEOUT)
            if hist is None or hist.empty:
                return None
            last = hist.iloc[-1]
            return hist.index[-1].date(), float(last["Close"])
        except Exception:
            return None

    def fetch_usd_to_hkd(self) -> float | None:
        res = self.fetch_close("HKD=X")
        return res[1] if res else None

    def fetch_fx_to_hkd(self, currency: str, d: date | None = None) -> float | None:
        if currency == "HKD":
            return 1.0
        if currency == "USD":
            return _hist_close("HKD=X", d)
        if currency == "CNY":
            usd_hkd = _hist_close("HKD=X", d)
            usd_cny = _hist_close("CNY=X", d)
            if usd_hkd and usd_cny:
                return usd_hkd / usd_cny
            return None
        return None


def _hist_close(ticker: str, d: date | None) -> float | None:
    """Latest daily close on or before d; latest available when d is None."""
    if yf is None:
        return None
    try:
        hist = yf.Ticker(ticker).history(period="3mo", timeout=HTTP_TIMEOUT)
        if hist is None or hist.empty:
            return None
        best = None
        for ts, row in hist.iterrows():
            if d is None or ts.date() <= d:
                best = float(row["Close"])
            elif d is not None:
                break
        return best
    except Exception:
        return None


class EastMoneyProvider(BaseProvider):
    """Unofficial East Money (东方财富) push2 API provider.

    Symbol mapping: Yahoo ticker -> East Money secid ("MktNum.Code",
    e.g. "106.SGOV", "116.03152") resolved via the public suggest API.
    Quote fields f43 latest, f44 high, f45 low, f46 open, f60 prev close
    (verified against live push2 responses 2026-10-02).
    """
    name = "eastmoney"

    _secid_cache: dict[str, str | None] = {}

    def _secid(self, symbol: str) -> str | None:
        """Map a Yahoo ticker to an East Money secid ("MktNum.Code").

        Yahoo strips HK leading zeros ("03152" -> "3152.HK"), so for HK
        tickers we also try the zero-padded form. Candidates are filtered
        by market (HK -> MktNum 116, US -> Classify UsStock) so that e.g.
        "3152" never resolves to the Taiwan stock 178.3152.
        """
        if symbol in self._secid_cache:
            return self._secid_cache[symbol]
        is_hk = symbol.upper().endswith(".HK")
        base = symbol[:-3] if is_hk else symbol
        queries = [base, base.zfill(5)] if is_hk else [base]
        secid = None
        for q in dict.fromkeys(queries):  # dedupe, keep order
            url = ("https://searchapi.eastmoney.com/api/suggest/get?input="
                   + urllib.parse.quote(q) + "&type=14")
            try:
                data = _http_get_json(url) or {}
                items = (data.get("QuotationCodeTable") or {}).get("Data") or []
            except Exception:
                items = []
            if is_hk:
                items = [i for i in items if i.get("MktNum") == "116"]
            else:
                items = [i for i in items if i.get("Classify") == "UsStock"]
            if not items:
                continue
            # prefer an exact code match, fall back to the first hit
            pick = next((i for i in items
                         if str(i.get("Code", "")).upper() == q.upper()), None)
            pick = pick or items[0]
            if pick and pick.get("QuoteID"):
                secid = str(pick["QuoteID"])
                break
        self._secid_cache[symbol] = secid
        return secid

    def fetch_close(self, symbol: str) -> tuple[date, float] | None:
        secid = self._secid(symbol)
        if not secid:
            return None
        url = ("https://push2.eastmoney.com/api/qt/stock/get?secid=" + secid
               + "&fields=f12,f14,f43,f44,f45,f46,f60")
        try:
            data = _http_get_json(url) or {}
            q = data.get("data") or {}
            price = q.get("f43")
            if price is None or price == "-":
                return None
            price = float(price)
            if price <= 0:
                return None
            # push2 stock/get carries no quote date; use today (documented limitation)
            return date.today(), price
        except Exception:
            return None

    def fetch_usd_to_hkd(self) -> float | None:
        return self.fetch_fx_to_hkd("USD")

    def fetch_fx_to_hkd(self, currency: str, d: date | None = None) -> float | None:
        # East Money has no reliable public forex endpoint. FX is served by
        # yfinance for every provider (it stays a hard dependency); the point
        # of the abstraction is that *callers* never import yfinance directly.
        try:
            return YFinanceProvider().fetch_fx_to_hkd(currency, d)
        except Exception:
            return None


def get_provider() -> BaseProvider:
    if config.MARKET_PROVIDER == "eastmoney":
        return EastMoneyProvider()
    return YFinanceProvider()


# ---- module-level facade (stable API for the rest of the app) ----
def fetch_close(symbol: str) -> tuple[date, float] | None:
    return get_provider().fetch_close(symbol)


def fetch_usd_to_hkd() -> float | None:
    return get_provider().fetch_usd_to_hkd()


_FX_CACHE: dict[tuple, tuple[float, float | None]] = {}
_FX_TTL_LATEST = 600.0  # seconds; portfolio_summary hits this on every view


def fetch_fx_to_hkd(currency: str, d: date | None = None) -> float | None:
    """HKD per 1 unit of currency, via the active provider.

    Latest rates are cached 10 minutes; historical dates are immutable so
    they are cached indefinitely (per process).
    """
    provider = get_provider()
    key = (provider.name, currency, d.isoformat() if d else "latest")
    now = time.monotonic()
    ttl = float("inf") if d and d < date.today() else _FX_TTL_LATEST
    if key in _FX_CACHE:
        ts, val = _FX_CACHE[key]
        if now - ts < ttl:
            return val
    val = provider.fetch_fx_to_hkd(currency, d)
    _FX_CACHE[key] = (now, val)
    return val


def refresh_all(db: Session) -> dict:
    """Pull latest closes for every instrument, upsert snapshots.

    Price fetches run concurrently (ThreadPoolExecutor) — the old serial
    loop took up to 15s * N instruments on timeouts. DB upserts stay
    sequential in the calling thread (SQLite-safe).
    """
    from concurrent.futures import ThreadPoolExecutor

    provider = get_provider()
    instruments = db.query(Instrument).all()

    def _fetch(inst) -> tuple:
        try:
            return inst, provider.fetch_close(inst.symbol)
        except Exception:
            return inst, None

    fetched: dict[int, tuple | None] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for inst, res in ex.map(_fetch, instruments):
            fetched[inst.id] = (inst, res)

    updated, failed = [], []
    for inst in instruments:
        _inst, res = fetched[inst.id]
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
            db.add(PriceSnapshot(instrument_id=inst.id, date=d, close=close,
                                 source=provider.name))
        updated.append(inst.symbol)
    db.commit()
    return {"provider": provider.name, "updated": updated, "failed": failed}
