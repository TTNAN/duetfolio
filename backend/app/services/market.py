"""Market data providers.

Architecture: every provider implements BaseProvider. The active provider is
chosen by the MARKET_PROVIDER env var ("yfinance" default, "eastmoney"
optional). Callers (refresh_all, portfolio engine) never touch a provider
directly — they use the module-level fetch_close / fetch_usd_to_hkd /
fetch_fx_to_hkd, which delegate to the active provider.

Quote fetching (refresh_all) always has backups: providers are tried in
order until one returns a quote — primary first, then the others in a fixed
preference order. The snapshot records which provider actually supplied
each quote.

- yfinance: official-ish, zero-setup, ~15min delayed quotes.
- eastmoney: unofficial push2.eastmoney.com API. Closer to real-time for
  CN-based investors and needs no API key, but it is undocumented and may
  break without notice. Any failure degrades to None (reported as "failed").
- sina: Sina Finance hq.sinajs.cn, designed for mainland China networks
  where Yahoo is blocked. Thinner fields; last resort.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import config
from app.models.models import Instrument, PriceSnapshot

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

HTTP_TIMEOUT = 15
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _http_get_json(url: str, timeout: int = HTTP_TIMEOUT) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None


def yahoo_ticker(symbol: str) -> str:
    """App symbol -> the ticker Yahoo actually serves.

    The app stores HK codes without leading zeros ("700.HK", "3152.HK"), but
    Yahoo needs at least 4 digits: "0700.HK", "0005.HK". 4- and 5-digit codes
    ("3152.HK", "9988.HK") are unchanged. Before this mapping, every HK code
    below 1000 (Tencent, HSBC, China Mobile...) silently failed on Yahoo.
    """
    s = symbol.upper()
    if s.endswith(".HK"):
        code = s[:-3].lstrip("0") or "0"
        return code.zfill(4) + ".HK"
    return s


class BaseProvider:
    name = "base"

    def fetch_close(self, symbol: str) -> tuple[date, float, float | None] | None:
        """Latest close for a Yahoo-format ticker (e.g. "SGOV", "3152.HK").

        Returns (quote_date, close, prev_close); prev_close may be None
        when the source doesn't provide it.
        """
        raise NotImplementedError

    def fetch_usd_to_hkd(self) -> float | None:
        """HKD per 1 USD."""
        raise NotImplementedError

    def fetch_fx_to_hkd(self, currency: str, d: date | None = None) -> float | None:
        """HKD per 1 unit of `currency`; on date d, or latest when d is None."""
        raise NotImplementedError


class YFinanceProvider(BaseProvider):
    name = "yfinance"

    def fetch_close(self, symbol: str) -> tuple[date, float, float | None] | None:
        if yf is None:
            return None
        try:
            hist = yf.Ticker(yahoo_ticker(symbol)).history(period="5d", timeout=config.YFINANCE_TIMEOUT)
            if hist is None or hist.empty:
                return None
            last = hist.iloc[-1]
            prev = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else None
            return hist.index[-1].date(), float(last["Close"]), prev
        except Exception:
            return None

    def fetch_usd_to_hkd(self) -> float | None:
        res = self.fetch_close("HKD=X")
        return res[1] if res else None

    def fetch_fx_to_hkd(self, currency: str, d: date | None = None) -> float | None:
        if currency == "HKD":
            return 1.0
        result = None
        if currency == "USD":
            result = _hist_close("HKD=X", d)
        elif currency == "CNY":
            usd_hkd = _hist_close("HKD=X", d)
            usd_cny = _hist_close("CNY=X", d)
            if usd_hkd and usd_cny:
                result = usd_hkd / usd_cny
        # Frankfurter fallback for latest rates when yfinance is unreachable
        # (e.g. Yahoo blocked). Latest only; historical still needs yfinance.
        if result is None and d is None:
            result = _frankfurter_fx_to_hkd(currency)
        return result


def _frankfurter_fx_to_hkd(currency: str) -> float | None:
    """Latest HKD per 1 unit of currency via Frankfurter API (free, no key)."""
    if currency == "HKD":
        return 1.0
    try:
        url = ("https://api.frankfurter.app/latest?from="
               + urllib.parse.quote(currency) + "&to=HKD")
        data = _http_get_json(url) or {}
        rate = (data.get("rates") or {}).get("HKD")
        return float(rate) if rate else None
    except Exception:
        return None


def _hist_close(ticker: str, d: date | None) -> float | None:
    """Latest daily close on or before d; latest available when d is None.

    The window is anchored on d (d-10 .. d+1) rather than "the last 3 months":
    the old period="3mo" query silently returned None for any trade older than
    ~90 days, so those trades fell back to today's FX.
    """
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        if d is None:
            hist = t.history(period="5d", timeout=HTTP_TIMEOUT)
        else:
            from datetime import timedelta
            hist = t.history(start=(d - timedelta(days=10)).isoformat(),
                             end=(d + timedelta(days=1)).isoformat(),
                             timeout=HTTP_TIMEOUT)
        if hist is None or hist.empty:
            return None
        best = None
        for ts, row in hist.iterrows():
            if d is None or ts.date() <= d:
                best = float(row["Close"])
            else:
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

    def fetch_close(self, symbol: str) -> tuple[date, float, float | None] | None:
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
            # East Money push2 returns US-stock quotes scaled x1000 (verified
            # live 2026-10-10: TSLA f43=382700 for a ~$382.70 quote). HK
            # quotes arrive in HKD directly and are left alone.
            is_us = not symbol.upper().endswith(".HK")
            if is_us:
                price = price / 1000
            prev = q.get("f60")
            prev = float(prev) if prev not in (None, "-") and float(prev) > 0 else None
            if is_us and prev is not None:
                prev = prev / 1000
            # push2 stock/get carries no quote date; use today (documented limitation)
            return date.today(), price, prev
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


class SinaProvider(BaseProvider):
    """Sina Finance (新浪财经) hq.sinajs.cn quote API.

    Designed for mainland China networks where Yahoo is blocked. No API key;
    requires a Referer header and GBK decoding.
    - US: "TSLA" -> gb_tsla; fields[1] latest, fields[4] change amount,
      prev close = latest - change; fields[3] datetime.
    - HK: "3152.HK" -> hk03152 (5-digit, zero-padded); fields[6] latest,
      fields[3] prev close; fields[17] date.
    FX is not served here (Frankfurter covers it); returns None.
    """
    name = "sina"

    def _sina_symbol(self, symbol: str) -> str | None:
        s = symbol.upper()
        if s.endswith(".HK"):
            return "hk" + s[:-3].zfill(5)
        if "." not in s:
            return "gb_" + s.lower()
        return None

    def fetch_close(self, symbol: str) -> tuple[date, float, float | None] | None:
        sina_sym = self._sina_symbol(symbol)
        if not sina_sym:
            return None
        try:
            req = urllib.request.Request(
                "https://hq.sinajs.cn/list=" + sina_sym,
                headers={"Referer": "https://finance.sina.com.cn"})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                text = resp.read().decode("gbk", errors="ignore")
            m = re.search(r'"([^"]*)"', text)
            if not m:
                return None
            f = m.group(1).split(",")
            if sina_sym.startswith("gb_"):
                if len(f) < 5 or not f[1]:
                    return None
                price = float(f[1])
                if price <= 0:
                    return None
                chg = float(f[4]) if f[4] else 0.0
                prev = price - chg if chg else None
                d = date.fromisoformat(f[3].split(" ")[0])
                return d, price, prev
            else:
                if len(f) < 18 or not f[6]:
                    return None
                price = float(f[6])
                if price <= 0:
                    return None
                prev = float(f[3]) if f[3] else None
                d = date.fromisoformat(f[17].replace("/", "-"))
                return d, price, prev if prev and prev > 0 else None
        except Exception:
            return None

    def fetch_usd_to_hkd(self) -> float | None:
        return None

    def fetch_fx_to_hkd(self, currency: str, d: date | None = None) -> float | None:
        return None


def get_provider() -> BaseProvider:
    if config.MARKET_PROVIDER == "eastmoney":
        return EastMoneyProvider()
    return YFinanceProvider()


# ---- module-level facade (stable API for the rest of the app) ----
def fetch_close(symbol: str) -> tuple[date, float, float | None] | None:
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


def refresh_all(db: Session, force: bool = False) -> dict:
    """Pull latest closes for every instrument, upsert snapshots.

    Price fetches run concurrently (ThreadPoolExecutor) — the old serial
    loop took up to 15s * N instruments on timeouts. DB upserts stay
    sequential in the calling thread (SQLite-safe).

    Quote TTL is persisted: an instrument whose latest snapshot was fetched
    less than QUOTE_TTL_SECONDS ago is skipped (reported under "fresh"),
    so the cache survives restarts and is shared by multiple workers.
    `force=True` ignores the TTL.
    """
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime as _dt, timezone as _tz

    from app import config as _cfg

    primary = get_provider()
    # Everyone else becomes a fallback, in a fixed preference order.
    # Sina last: it works in CN but its fields are thinner than the others.
    _all = [YFinanceProvider(), EastMoneyProvider(), SinaProvider()]
    chain = [primary] + [p for p in _all if p.name != primary.name]
    instruments = db.query(Instrument).all()
    fresh: list[str] = []
    if not force and _cfg.QUOTE_TTL_SECONDS > 0:
        now_ = _dt.now(_tz.utc).replace(tzinfo=None)
        last = dict(db.query(PriceSnapshot.instrument_id, func.max(PriceSnapshot.fetched_at))
                    .group_by(PriceSnapshot.instrument_id).all())
        keep = []
        for inst in instruments:
            ts = last.get(inst.id)
            if ts is not None:
                ts = ts.replace(tzinfo=None) if ts.tzinfo else ts
                if (now_ - ts).total_seconds() < _cfg.QUOTE_TTL_SECONDS:
                    fresh.append(inst.symbol)
                    continue
            keep.append(inst)
        instruments = keep

    def _fetch(inst) -> tuple:
        """Try each provider in order. Returns (inst, result, source)."""
        for prov in chain:
            try:
                res = prov.fetch_close(inst.symbol)
            except Exception:
                res = None
            if res is not None:
                return inst, res, prov.name
        return inst, None, None

    fetched: dict[int, tuple | None] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for inst, res, src in ex.map(_fetch, instruments):
            fetched[inst.id] = (inst, res, src)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    updated, failed = [], []
    for inst in instruments:
        _inst, res, src = fetched[inst.id]
        if res is None:
            failed.append(inst.symbol)
            continue
        d, close, prev_close = res[0], res[1], res[2] if len(res) > 2 else None
        snap = (
            db.query(PriceSnapshot)
            .filter_by(instrument_id=inst.id, date=d)
            .one_or_none()
        )
        if snap:
            snap.close = close
            snap.prev_close = prev_close
            snap.source = src
            snap.fetched_at = now
        else:
            db.add(PriceSnapshot(instrument_id=inst.id, date=d, close=close,
                                 prev_close=prev_close, source=src,
                                 fetched_at=now))
        updated.append(inst.symbol)
    db.commit()
    return {"provider": primary.name,
            "fallbacks": [p.name for p in chain[1:]],
            "updated": updated, "failed": failed, "fresh": fresh}


# ---- daily history (backfill + benchmarks) ----
def _yf_daily(symbol: str, start: date) -> list[tuple[date, float]]:
    if yf is None:
        return []
    try:
        hist = yf.Ticker(yahoo_ticker(symbol)).history(start=start.isoformat(), interval="1d",
                                         auto_adjust=False,
                                         timeout=config.YFINANCE_TIMEOUT)
        if hist is None or hist.empty:
            return []
        return [(ts.date(), float(row["Close"])) for ts, row in hist.iterrows()
                if row["Close"] == row["Close"]]  # drop NaN
    except Exception:
        return []


def _eastmoney_daily(symbol: str, start: date) -> list[tuple[date, float]]:
    """East Money push2his daily kline (unadjusted). Best-effort fallback for
    networks where Yahoo is blocked; kline prices are in real units."""
    secid = EastMoneyProvider()._secid(symbol)
    if not secid:
        return []
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=" + secid
           + "&fields1=f1,f2,f3&fields2=f51,f53&klt=101&fqt=0&beg="
           + start.strftime("%Y%m%d") + "&end=20500101")
    data = _http_get_json(url) or {}
    out = []
    for line in ((data.get("data") or {}).get("klines") or []):
        try:
            d_s, c_s = line.split(",")[:2]
            out.append((date.fromisoformat(d_s), float(c_s)))
        except Exception:
            continue
    return out


def fetch_daily_history(symbol: str, start: date) -> tuple[list[tuple[date, float]], str | None]:
    """Daily closes from `start` to today. Yahoo first, East Money fallback."""
    rows = _yf_daily(symbol, start)
    if rows:
        return rows, "yfinance"
    rows = _eastmoney_daily(symbol, start)
    if rows:
        return rows, "eastmoney"
    return [], None


def backfill_history(db: Session, only: list[int] | None = None, commit: bool = True) -> dict:
    """Fill daily closes from each instrument's first trade date to today.

    Only INSERTS missing dates — existing snapshots (live quotes with
    prev_close / fetched_at) are never overwritten. Lets the net-worth curve
    show real history immediately instead of "refresh a few times".
    """
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import func

    from app.models.models import Transaction

    firsts = dict(db.query(Transaction.instrument_id, func.min(Transaction.date))
                  .group_by(Transaction.instrument_id).all())
    instruments = [i for i in db.query(Instrument).all()
                   if i.id in firsts and (only is None or i.id in only)]

    def _fetch(inst):
        rows, src = fetch_daily_history(inst.symbol, firsts[inst.id])
        return inst, rows, src

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_fetch, instruments))

    filled, failed, inserted = [], [], 0
    for inst, rows, src in results:
        if not rows:
            failed.append(inst.symbol)
            continue
        have = {d for (d,) in db.query(PriceSnapshot.date)
                .filter_by(instrument_id=inst.id).all()}
        for d_, close in rows:
            if d_ in have:
                continue
            db.add(PriceSnapshot(instrument_id=inst.id, date=d_, close=close,
                                 source=f"{src}-hist"))
            have.add(d_)
            inserted += 1
        filled.append(inst.symbol)
    if commit:
        db.commit()
    else:
        db.flush()
    return {"filled": filled, "failed": failed, "inserted": inserted}


_BENCH_CACHE: dict[tuple, tuple[float, list]] = {}
BENCHMARKS = {
    "SPY": "S&P 500 (SPY)",
    "QQQ": "Nasdaq-100 (QQQ)",
    "2800.HK": "Hang Seng (2800.HK)",
    "3033.HK": "HS TECH (3033.HK)",
}


def benchmark_series(symbol: str, start: date) -> tuple[list[tuple[date, float]], str | None]:
    """Daily closes of a benchmark, cached 1 hour per (symbol, start)."""
    key = (symbol, start.isoformat())
    now = time.monotonic()
    if key in _BENCH_CACHE and now - _BENCH_CACHE[key][0] < 3600:
        return _BENCH_CACHE[key][1]
    res = fetch_daily_history(symbol, start)
    if res[0]:
        _BENCH_CACHE[key] = (now, res)
    return res


# ---- symbol search (for the "add instrument" flow) ----
_US_EXCHANGES = {"NMS", "NYQ", "NGM", "ASE", "NAS", "NYS", "PCX", "BTS"}
_HK_EXCHANGES = {"HKG"}
_SEARCH_TIMEOUT = 8  # interactive; fail fast rather than hang the UI


def _yahoo_search(query: str) -> list[dict]:
    """Yahoo Finance search API (no key). Filters to US/HK equity+ETF."""
    url = ("https://query1.finance.yahoo.com/v1/finance/search?q="
           + urllib.parse.quote(query))
    data = _http_get_json(url, timeout=_SEARCH_TIMEOUT) or {}
    out = []
    for q in data.get("quotes") or []:
        if q.get("quoteType") not in ("EQUITY", "ETF"):
            continue
        ex = (q.get("exchange") or "").upper()
        sym = (q.get("symbol") or "").upper()
        name = q.get("longname") or q.get("shortname") or sym
        if ex in _US_EXCHANGES and sym:
            out.append({"symbol": sym, "name": name, "market": "US",
                        "currency": "USD", "source": "yahoo"})
        elif ex in _HK_EXCHANGES and sym:
            # normalize to the app's Yahoo convention: 03152 -> 3152.HK
            base = sym[:-3] if sym.endswith(".HK") else sym
            norm = (base.lstrip("0") or "0") + ".HK"
            out.append({"symbol": norm, "name": name, "market": "HK",
                        "currency": "HKD", "source": "yahoo"})
    return out


def _eastmoney_search(query: str) -> list[dict]:
    """East Money suggest API. Keeps HK (MktNum 116) and US (UsStock) only —
    mainland funds/A-shares are outside this app's scope.

    Two queries run concurrently: an unfiltered one (catches US stocks and
    exact code matches) plus an HK-only one (mktnum=116). The HK-only query
    matters because mainland funds crowd HK ETFs out of the ranking — e.g.
    "博时" would otherwise never surface 03152 (A博时港元).
    """
    base = ("https://searchapi.eastmoney.com/api/suggest/get?input="
            + urllib.parse.quote(query) + "&type=14")
    urls = [base + "&count=50", base + "&mktnum=116&count=50"]

    def _fetch(url: str) -> dict:
        return _http_get_json(url, timeout=_SEARCH_TIMEOUT) or {}

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        datas = list(ex.map(_fetch, urls))

    out = []
    for data in datas:
        items = (data.get("QuotationCodeTable") or {}).get("Data") or []
        for i in items:
            if i.get("MktNum") == "116":
                code = str(i.get("Code") or "").lstrip("0") or "0"
                out.append({"symbol": f"{code}.HK",
                            "name": str(i.get("Name") or ""),
                            "market": "HK", "currency": "HKD",
                            "source": "eastmoney"})
            elif i.get("Classify") == "UsStock":
                out.append({"symbol": str(i.get("Code") or "").upper(),
                            "name": str(i.get("Name") or ""),
                            "market": "US", "currency": "USD",
                            "source": "eastmoney"})
    return out


def search_instruments(query: str, limit: int = 20) -> list[dict]:
    """Candidate instruments for the add-instrument search box.

    Queries Yahoo and East Money concurrently, dedupes by normalized
    symbol (Yahoo first). Any single source failing degrades to the other.
    """
    from concurrent.futures import ThreadPoolExecutor

    query = (query or "").strip()
    if not query:
        return []
    with ThreadPoolExecutor(max_workers=2) as ex:
        yh = ex.submit(_yahoo_search, query)
        em = ex.submit(_eastmoney_search, query)
        results = (yh.result() or []) + (em.result() or [])
    seen, out = set(), []
    for r in results:
        if r["symbol"] in seen:
            continue
        seen.add(r["symbol"])
        out.append(r)
        if len(out) >= limit:
            break
    return out
