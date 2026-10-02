"""Market data providers.

Architecture: every provider implements BaseProvider. The active provider is
chosen by the MARKET_PROVIDER env var ("yfinance" default, "eastmoney"
optional). Callers (refresh_all, portfolio engine) never touch a provider
directly — they use the module-level fetch_close / fetch_usd_to_hkd, which
delegate to the active provider.

- yfinance: official-ish, zero-setup, ~15min delayed quotes.
- eastmoney: unofficial push2.eastmoney.com API. Closer to real-time for
  CN-based investors and needs no API key, but it is undocumented and may
  break without notice. Any failure degrades to None (reported as "failed").
"""
import json
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
        # East Money forex coverage is inconsistent; reuse yfinance when present.
        if yf is not None:
            try:
                return YFinanceProvider().fetch_usd_to_hkd()
            except Exception:
                return None
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


def refresh_all(db: Session) -> dict:
    """Pull latest closes for every instrument, upsert snapshots."""
    provider = get_provider()
    instruments = db.query(Instrument).all()
    updated, failed = [], []
    for inst in instruments:
        res = provider.fetch_close(inst.symbol)
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
