"""Broker CSV import: map Futu / IBKR / generic trade exports to transactions.

Two formats:
1. Generic table (Futu and most brokers): a header row with recognizable
   columns (Chinese or English), one trade per row.
2. IBKR Activity statement: multi-section CSV; we parse the "Trades" section.

Column detection is keyword-based so minor header variations still work.
Symbols are normalized to the app's Yahoo convention ("700.HK", "AAPL").
Unknown instruments are auto-created on confirm (not on preview).
"""
import csv
import io
import re
from datetime import date, datetime

HEADER_KEYS = {
    "symbol": [r"证券代码", r"代码", r"symbol", r"ticker", r"stock.*code"],
    "side": [r"买卖方向", r"交易方向", r"方向", r"买卖", r"\bside\b", r"\btype\b", r"操作"],
    "quantity": [r"成交数量", r"数量", r"quantity", r"\bqty\b", r"股数", r"shares"],
    "price": [r"成交价格", r"成交均价", r"价格", r"\bprice\b", r"trade.*price", r"t\.\s*price"],
    "date": [r"成交时间", r"交易时间", r"时间", r"日期", r"\bdate", r"datetime"],
    "fee": [r"手续费", r"佣金", r"费用", r"\bfee\b", r"commission", r"comm"],
    "market": [r"市场", r"\bmarket\b", r"exchange", r"交易所"],
    "name": [r"证券名称", r"名称", r"\bname\b"],
}

SIDE_MAP = [
    (re.compile(r"买入|买\b|^b$|^buy$", re.I), "buy"),
    (re.compile(r"卖出|卖\b|^s$|^sell$", re.I), "sell"),
    (re.compile(r"分红|派息|dividend|div\b", re.I), "dividend"),
]

SKIP_SIDE = re.compile(r"存入|取出|转账|转入|转出|利息|deposit|withdraw|transfer|interest|fee|tax", re.I)

DATE_FMTS = [
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y",
]


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "gbk", "big5"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _find_col(headers: list[str], key: str) -> int | None:
    for i, h in enumerate(headers):
        h = (h or "").strip().lower()
        if any(re.search(p, h) for p in HEADER_KEYS[key]):
            return i
    return None


def _parse_date(s: str) -> date | None:
    s = (s or "").strip().split(",")[0].strip()
    # IBKR "2026-09-30, 13:00:00" -> date part before comma
    for f in DATE_FMTS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _num(s: str) -> float | None:
    s = (s or "").strip().replace(",", "")
    if not s or s in ("-", "--", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize_symbol(raw_sym: str, raw_mkt: str = "") -> tuple[str, str, str] | None:
    """-> (symbol, market, currency) in app convention, or None if unsupported."""
    s = (raw_sym or "").strip().upper()
    m = (raw_mkt or "").strip().upper()
    # strip common exchange prefixes/suffixes: HK.00700, 00700.HK, 700.SEHK
    s = re.sub(r"^(HK|HKG|SEHK)[.:]", "", s)
    s = re.sub(r"[.](HK|HKG|SEHK)$", "", s)
    is_hk = ("HK" in m or "SEHK" in m or "HKG" in m
             or re.fullmatch(r"\d{1,6}", s) is not None and ("US" not in m and "NASDAQ" not in m and "NYSE" not in m and "AMEX" not in m))
    # a bare 1-6 digit code with no market info defaults to HK (Futu style)
    if re.fullmatch(r"\d{1,6}", s or ""):
        if "US" in m or "NASDAQ" in m or "NYSE" in m or "AMEX" in m:
            is_hk = False
        else:
            is_hk = True
    if is_hk:
        code = s.lstrip("0") or "0"
        return f"{code}.HK", "HK", "HKD"
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]*", s or ""):
        return s, "US", "USD"
    return None


def _map_side(v: str) -> str | None:
    v = (v or "").strip()
    for rx, side in SIDE_MAP:
        if rx.search(v):
            return side
    return None


def _row_to_txn(cells: list[str], cols: dict, lineno: int) -> dict:
    """Parse one generic-table row -> candidate dict or error/skip marker."""
    get = lambda k: cells[cols[k]].strip() if cols.get(k) is not None and cols[k] < len(cells) else ""
    raw_side = get("side")
    if raw_side and SKIP_SIDE.search(raw_side):
        return {"status": "skip", "reason": f"非交易行（{raw_side}）", "lineno": lineno}
    side = _map_side(raw_side)
    if not side:
        return {"status": "error", "reason": f"无法识别方向：{raw_side!r}", "lineno": lineno}
    norm = normalize_symbol(get("symbol"), get("market"))
    if not norm:
        return {"status": "error", "reason": f"无法识别代码：{get('symbol')!r}", "lineno": lineno}
    qty = _num(get("quantity"))
    price = _num(get("price"))
    d = _parse_date(get("date"))
    if qty is None or qty == 0:
        return {"status": "error", "reason": "数量缺失", "lineno": lineno}
    if price is None:
        return {"status": "error", "reason": "价格缺失", "lineno": lineno}
    if d is None:
        return {"status": "error", "reason": f"日期无法解析：{get('date')!r}", "lineno": lineno}
    symbol, market, currency = norm
    fee = _num(get("fee")) or 0.0
    return {
        "status": "ok", "lineno": lineno,
        "symbol": symbol, "name": get("name"), "market": market,
        "currency": currency, "type": side,
        "quantity": abs(qty), "price": price, "fee": abs(fee), "date": d.isoformat(),
    }


def _parse_ibkr(rows: list[list[str]]) -> list[dict]:
    """IBKR Activity statement: parse the Trades section.

    Section layout:  Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,Comm/Fee,...
                     Trades,Data,Order,Stocks,USD,AAPL,"2026-09-30, 13:00:00",10,232.5,-1,...
    """
    header = None
    for r in rows:
        if len(r) > 2 and r[0].strip() == "Trades" and r[1].strip().lower() == "header":
            header = [c.strip() for c in r]
            break
    if not header:
        return [{"status": "error", "reason": "IBKR 文件里没找到 Trades 表头", "lineno": 0}]
    idx = {c.lower(): i for i, c in enumerate(header)}

    def col(*names):
        for n in names:
            if n in idx:
                return idx[n]
        return None

    c_sym, c_dt = col("symbol"), col("date/time")
    c_qty, c_px = col("quantity"), col("t. price")
    c_fee, c_ccy = col("comm/fee"), col("currency")
    c_ex = col("exchange")
    out = []
    for ln, r in enumerate(rows, 1):
        if len(r) < 3 or r[0].strip() != "Trades" or r[1].strip().lower() != "data":
            continue
        if len(r) > 2 and r[2].strip().lower() == "total":
            continue
        qty = _num(r[c_qty]) if c_qty is not None and c_qty < len(r) else None
        if qty is None or qty == 0:
            continue
        norm = normalize_symbol(r[c_sym] if c_sym is not None and c_sym < len(r) else "",
                                r[c_ex] if c_ex is not None and c_ex < len(r) else "")
        if not norm:
            out.append({"status": "error", "reason": f"无法识别代码：{r[c_sym]!r}", "lineno": ln})
            continue
        symbol, market, currency = norm
        d = _parse_date(r[c_dt] if c_dt is not None and c_dt < len(r) else "")
        price = _num(r[c_px]) if c_px is not None and c_px < len(r) else None
        fee = abs(_num(r[c_fee]) if c_fee is not None and c_fee < len(r) else 0.0) or 0.0
        if d is None or price is None:
            out.append({"status": "error", "reason": "日期/价格缺失", "lineno": ln})
            continue
        out.append({
            "status": "ok", "lineno": ln,
            "symbol": symbol, "name": "", "market": market, "currency": currency,
            "type": "buy" if qty > 0 else "sell",
            "quantity": abs(qty), "price": price, "fee": fee, "date": d.isoformat(),
        })
    return out


def parse_csv(raw: bytes) -> dict:
    """Parse an uploaded broker CSV -> {"rows": [...], "format": ...}."""
    text = _decode(raw)
    rows = [r for r in csv.reader(io.StringIO(text)) if any((c or "").strip() for c in r)]
    if not rows:
        return {"rows": [], "format": "empty"}
    first = [(c or "").strip() for c in rows[0]]
    if first and first[0] in ("Trades", "Statement"):
        return {"rows": _parse_ibkr(rows), "format": "ibkr"}
    headers = first
    cols = {k: _find_col(headers, k) for k in HEADER_KEYS}
    if cols["symbol"] is None or cols["quantity"] is None or cols["price"] is None:
        return {"rows": [{"status": "error", "lineno": 1,
                          "reason": "表头识别失败：至少需要代码/数量/价格列"}], "format": "unknown"}
    out = []
    for ln, r in enumerate(rows[1:], 2):
        out.append(_row_to_txn([(c or "") for c in r], cols, ln))
    return {"rows": out, "format": "table"}
