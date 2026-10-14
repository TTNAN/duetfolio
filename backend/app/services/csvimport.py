"""Broker CSV import: map Futu / Tiger / IBKR / Schwab / generic exports.

Formats (auto-detected, or forced with `broker=`):
1. Futu (富途牛牛/moomoo) and Tiger (老虎) order/trade exports, plus any
   generic table: a header row with recognizable columns (Chinese or
   English), one trade per row. Filled quantity/price/time columns win over
   order quantity/price/time; multiple fee columns are summed unless a
   total-fee column exists.
2. IBKR Activity statement: multi-section CSV; we parse the "Trades" section.
3. Charles Schwab "Transactions" export: Date/Action/Symbol/Quantity/Price/
   Fees & Comm/Amount, with $-formatted numbers; buys, sells, reinvestments
   and cash dividends are mapped, transfers/interest are skipped.

Column detection is keyword-based so minor header variations still work.
Symbols are normalized to the app's Yahoo convention ("700.HK", "AAPL").
Unknown instruments are auto-created on confirm (not on preview).
"""
import csv
import io
import re
from datetime import date, datetime

# Patterns are in PRIORITY order: the first pattern that matches any header
# wins, so "成交数量" (filled) beats "订单数量" (ordered) in Futu exports.
HEADER_KEYS = {
    "symbol": [r"证券代码", r"股票代码", r"^代码$", r"代码", r"symbol", r"ticker", r"stock.*code"],
    "side": [r"买卖方向", r"交易方向", r"^方向$", r"方向", r"买卖", r"\bside\b", r"\btype\b", r"操作", r"\baction\b"],
    "quantity": [r"成交数量", r"成交股数", r"已成交", r"^数量$", r"数量", r"quantity", r"\bqty\b", r"股数", r"shares"],
    "price": [r"成交价格", r"成交均价", r"成交价", r"^价格$", r"价格", r"trade.*price", r"t\.\s*price", r"\bprice\b"],
    "date": [r"成交时间", r"成交日期", r"交易时间", r"交易日期", r"^时间$", r"时间", r"日期", r"\bdate", r"datetime"],
    "fee": [r"合计费用", r"总费用", r"费用合计", r"手续费合计", r"手续费", r"佣金", r"费用", r"\bfee", r"commission", r"comm"],
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
    hs = [(h or "").strip().lower() for h in headers]
    for p in HEADER_KEYS[key]:
        for i, h in enumerate(hs):
            if re.search(p, h):
                return i
    return None


# itemized fee columns (Tiger / Futu HK list each charge separately)
FEE_PARTS = re.compile(r"佣金|手续费|平台费|交收费|印花税|交易费|交易征费|证监会征费|财汇局征费|"
                       r"结算费|活动费|其他费用|commission|platform fee|sec fee|taf|"
                       r"stamp duty|trading fee|settlement fee", re.I)
FEE_TOTAL = re.compile(r"合计费用|总费用|费用合计|手续费合计|total fee|fees? total|fees & comm", re.I)


def _fee_cols(headers: list[str]) -> list[int]:
    hs = [(h or "").strip() for h in headers]
    total = [i for i, h in enumerate(hs) if FEE_TOTAL.search(h)]
    if total:
        return total[:1]
    return [i for i, h in enumerate(hs) if FEE_PARTS.search(h)]


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
    """'1,234.5' / '$1,234.50' / '-$12.00' / '(12.00)' / 'HK$3.2' -> float."""
    s = (s or "").strip().replace(",", "").replace(" ", "")
    if not s or s in ("-", "--", "N/A", "n/a"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"^(-?)(?:US|HK)?\$", r"\1", s)
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def normalize_symbol(raw_sym: str, raw_mkt: str = "") -> tuple[str, str, str] | None:
    """-> (symbol, market, currency) in app convention, or None if unsupported."""
    s = (raw_sym or "").strip().upper()
    m = (raw_mkt or "").strip().upper()
    # Chinese market labels used by Futu / Tiger exports
    if "港" in m:
        m += " HK"
    if "美" in m:
        m += " US"
    s = re.sub(r"^(US)[.:]", "", s)
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
    if cols.get("_fees"):
        fee = sum(abs(_num(cells[i]) or 0.0) for i in cols["_fees"] if i < len(cells))
    else:
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


SCHWAB_BUY = re.compile(r"^(buy|reinvest shares|buy to open|buy to close)$", re.I)
SCHWAB_SELL = re.compile(r"^(sell|sell to open|sell to close|sell short)$", re.I)
SCHWAB_DIV = re.compile(r"dividend|qual div|non-qualified div|cash div|pr yr div|special div|cap gain", re.I)
SCHWAB_SKIP = re.compile(r"tax|wire|moneylink|transfer|journal|interest|fee|deposit|withdraw|"
                         r"security transfer|adr mgmt|service", re.I)


def _is_schwab(headers: list[str]) -> bool:
    hs = {h.strip().lower() for h in headers}
    return {"date", "action", "symbol"} <= hs and ("fees & comm" in hs or "amount" in hs)


def _parse_schwab(rows: list[list[str]], header_idx: int) -> list[dict]:
    headers = [h.strip().lower() for h in rows[header_idx]]
    ix = {h: i for i, h in enumerate(headers)}
    get = lambda r, k: (r[ix[k]].strip() if k in ix and ix[k] < len(r) else "")
    out = []
    for ln, r in enumerate(rows[header_idx + 1:], header_idx + 2):
        action = get(r, "action")
        if not action or get(r, "date").lower().startswith("transactions total"):
            continue
        d = _parse_date(get(r, "date").split(" as of ")[0])
        if SCHWAB_BUY.match(action) or SCHWAB_SELL.match(action):
            side = "buy" if SCHWAB_BUY.match(action) else "sell"
        elif SCHWAB_DIV.search(action) and not re.search(r"reinvest shares", action, re.I):
            side = "dividend"
        elif re.search(r"split", action, re.I):
            out.append({"status": "error", "lineno": ln,
                        "reason": "拆股请在 duetfolio 里手动记一笔「拆合股」（填比例）"})
            continue
        elif SCHWAB_SKIP.search(action):
            out.append({"status": "skip", "lineno": ln, "reason": f"非交易行（{action}）"})
            continue
        else:
            out.append({"status": "skip", "lineno": ln, "reason": f"未支持的类型（{action}）"})
            continue
        norm = normalize_symbol(get(r, "symbol"), "US")
        if not norm:
            out.append({"status": "error", "lineno": ln, "reason": f"无法识别代码：{get(r, 'symbol')!r}"})
            continue
        if d is None:
            out.append({"status": "error", "lineno": ln, "reason": f"日期无法解析：{get(r, 'date')!r}"})
            continue
        symbol, market, currency = norm
        fee = abs(_num(get(r, "fees & comm")) or 0.0)
        if side == "dividend":
            amt = _num(get(r, "amount"))
            if not amt:
                out.append({"status": "error", "lineno": ln, "reason": "分红金额缺失"})
                continue
            # Schwab reports only the cash amount: record as 1 x amount
            out.append({"status": "ok", "lineno": ln, "symbol": symbol, "name": get(r, "description"),
                        "market": market, "currency": currency, "type": "dividend",
                        "quantity": 1.0, "price": abs(amt), "fee": 0.0, "date": d.isoformat()})
            continue
        qty, price = _num(get(r, "quantity")), _num(get(r, "price"))
        if not qty or price is None:
            out.append({"status": "error", "lineno": ln, "reason": "数量/价格缺失"})
            continue
        out.append({"status": "ok", "lineno": ln, "symbol": symbol, "name": get(r, "description"),
                    "market": market, "currency": currency, "type": side,
                    "quantity": abs(qty), "price": abs(price), "fee": fee, "date": d.isoformat()})
    return out


BROKERS = ("auto", "futu", "tiger", "ibkr", "schwab", "generic")


def parse_csv(raw: bytes, broker: str = "auto") -> dict:
    """Parse an uploaded broker CSV -> {"rows": [...], "format": ...}."""
    text = _decode(raw)
    rows = [r for r in csv.reader(io.StringIO(text)) if any((c or "").strip() for c in r)]
    if not rows:
        return {"rows": [], "format": "empty"}
    broker = broker if broker in BROKERS else "auto"
    first = [(c or "").strip() for c in rows[0]]
    if broker == "ibkr" or (broker == "auto" and first and first[0] in ("Trades", "Statement")):
        return {"rows": _parse_ibkr(rows), "format": "ibkr"}
    # Schwab files may start with a title line ("Transactions for account ...")
    if broker in ("auto", "schwab"):
        for hi, r in enumerate(rows[:5]):
            if _is_schwab([(c or "") for c in r]):
                return {"rows": _parse_schwab(rows, hi), "format": "schwab"}
        if broker == "schwab":
            return {"rows": [{"status": "error", "lineno": 1,
                              "reason": "不是嘉信 (Schwab) 交易导出：缺少 Date/Action/Symbol 列"}],
                    "format": "schwab"}
    # Futu / Tiger / generic: the header may sit below a title line
    hi = 0
    for i, r in enumerate(rows[:5]):
        cand = [(c or "").strip() for c in r]
        if _find_col(cand, "symbol") is not None and _find_col(cand, "quantity") is not None:
            hi = i
            break
    rows = rows[hi:]
    headers = [(c or "").strip() for c in rows[0]]
    cols = {k: _find_col(headers, k) for k in HEADER_KEYS}
    cols["_fees"] = _fee_cols(headers)
    fmt = broker if broker in ("futu", "tiger", "generic") else "table"
    if cols["symbol"] is None or cols["quantity"] is None or cols["price"] is None:
        return {"rows": [{"status": "error", "lineno": 1,
                          "reason": "表头识别失败：至少需要代码/数量/价格列"}], "format": "unknown"}
    out = []
    for ln, r in enumerate(rows[1:], hi + 2):
        out.append(_row_to_txn([(c or "") for c in r], cols, ln))
    return {"rows": out, "format": fmt}
