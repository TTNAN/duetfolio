**English** | [简体中文](README.md)

# duetfolio ◈

**Holding both US and HK stocks? One glance tells you the total P&L in your home currency.**

![duetfolio dashboard](assets/dashboard.png)

---

## What it is

duetfolio is a portfolio tracker that runs on your own computer, built for people who hold **both US and Hong Kong stocks**:

- Both markets' positions on one screen — no more switching between broker apps
- USD and HKD holdings auto-converted into your base currency (HKD / USD / CNY)
- Every buy, sell and dividend timestamped and sized into a true **annualized return (XIRR)** — not just "up a few percent"

No sign-up, no data uploads. Your ledger lives in a local SQLite file. Dark/light mode toggle top-right.

## 3-minute start (Windows)

1. Install Python ([official site](https://www.python.org/downloads/), tick **Add python.exe to PATH**)
2. Click the green **Code** button → **Download ZIP**, extract
3. Open PowerShell in the project folder and run **`& .\start.ps1`** (wait for dependencies on first run), your dashboard opens in the browser

> If it says scripts are disabled, run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once (type `Y`), then the command above.
> It opens [http://127.0.0.1:8000](http://127.0.0.1:8000) — the backend also serves the frontend, so **only one window** stays open. Close it to stop.
> Alternative: double-click `start.bat` (the batch window may flash-close on some systems; use the PowerShell method instead).
> API docs only: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
> Manual frontend dev: `cd frontend && npm install && npm run dev` (Node.js 18+, page then lives on `:5173`)

## Your first entry

**① Add an instrument** — open the Instruments tab, search `03152`, `SGOV`, `腾讯` or `博时`, click a result to auto-fill symbol, market and currency, save.

**② Record a buy** — open the Transactions tab, pick the instrument, enter quantity, price and date, save. Position size and average cost are computed for you.

**③ Refresh quotes** — hit "Refresh" on the dashboard: total value, P&L and XIRR appear, with a "quotes as of" timestamp next to the button.

> Lots of trades? Transactions → **Import broker CSV** supports Futu / IBKR exports — preview first, confirm to write; unknown tickers auto-create instruments.
> Deposits/withdrawals? The **Cash** card at the bottom of Transactions records money in/out, and XIRR counts it — the annualized figure becomes "what this money earned", not just "what these tickers earned".

## FAQ

**How do I write HK symbols?**
Just search and click — no manual formatting needed. If you type them: Yahoo format strips leading zeros, `03152` → `3152.HK`, `00700` → `700.HK`; US tickers as-is (`AAPL`, `SGOV`).

**How is total P&L computed?**
Total P&L = unrealized (price − remaining cost basis) + realized (sells and dividends, net of fees). "Invested" on the page is the cost of the **currently held** position, not lifetime deposits.

**Why is XIRR absurdly large?**
XIRR is annualized — 0.1% over 4 days annualizes to a wild number. That's math, not a bug; it settles as the holding period grows. Each flow converts FX at the **transaction date's** rate (captured automatically), so FX noise never leaks into investment returns.

**How good are the quotes?**
**East Money** by default (closer to real-time); if it misses a symbol, **Yahoo Finance** fills in (~15 min delayed). Every quote records its actual source, shown next to "quotes as of".

**How is the net-worth curve drawn?**
Daily total = that day's position sizes × that day's closes, replayed from stored snapshots only (no live fetching). Historical days convert FX at **today's** rate — curve shape is trustworthy, old absolute values are approximate (noted next to the chart).

**Where is my data?**
Local SQLite file (`backend/duetfolio.db`). Nothing leaves your machine.

---

## Architecture (for developers)

```
frontend/  React 18 + Vite, hand-rolled SVG charts (zero chart deps)
backend/   FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2
db         SQLite (zero-config default) / PostgreSQL (via DATABASE_URL)
```

### Conventions

- **Positions & cost**: average-cost method. Buys scale cost up proportionally, sells release it proportionally, cost hits exactly zero on full exit (never negative).
- **XIRR**: pure-Python Newton solver (`backend/app/services/xirr.py`). Flows: buys (negative, incl. fees) / sells & dividends (positive, net of fees) / cash deposits (negative) / withdrawals (positive); terminal value dated at the **latest quote date**, not today (avoids annualization inflation). Returns null on <2 flows or single-signed flows — never forced.
- **FX**: each transaction captures the **trade-date** FX into `fx_to_hkd`; XIRR flows convert at that rate. Latest rates cached 10 min TTL.
- **Missing-data circuit breaker**: if any holding lacks a quote or any currency lacks FX, totals and XIRR go null (with a banner naming the gaps) — no "partially trustworthy" numbers.

### Market-data design

`BaseProvider` abstraction in `backend/app/services/market.py`, switched by `MARKET_PROVIDER` (default `yfinance`, `eastmoney` optional).

- **Primary/backup chain**: `refresh_all` tries the primary provider per symbol, then the backup before marking failed. Snapshots record the **actual** `source`/`fetched_at`, which the dashboard's "quotes as of" label reads.
- **eastmoney**: unofficial push2 API (`f43` latest / `f60` prev close); symbols mapped via the suggest API (`3152.HK` → `116.03152`, leading zeros restored); FX via yfinance (East Money has no reliable forex endpoint).
- **Symbol search**: `GET /api/instruments/search` queries Yahoo search + East Money suggest concurrently (generic + `mktnum=116` HK-only pass, so mainland funds can't crowd HK ETFs out of the ranking), dedupes, keeps US/HK only.

### API reference

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | liveness |
| GET/POST/DELETE | `/api/instruments…` | instruments |
| GET | `/api/instruments/search?q=` | fuzzy symbol/CJK-name search |
| GET/POST/PUT/DELETE | `/api/transactions…` | flows, incl. inline edit |
| POST | `/api/transactions/import/preview` | broker CSV parse preview (Futu/IBKR/generic) |
| POST | `/api/transactions/import` | confirm import (unknown tickers auto-created) |
| GET/POST/DELETE | `/api/cash…` | deposits/withdrawals |
| GET | `/api/portfolio/summary?base=` | totals, XIRR, dividends, holdings |
| GET | `/api/portfolio/history?base=` | net-worth curve points |
| POST | `/api/prices/refresh` | refresh all quotes (8-thread pool) |

Interactive docs at `/docs` once the backend is running.

### Local development

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload   # migrations run automatically on boot
.venv/bin/python -m pytest tests/         # 24 tests

cd ../frontend
npm install && npm run dev
```

### Configuration (env vars)

| Variable | Default | Notes |
|---|---|---|
| `MARKET_PROVIDER` | `yfinance` | primary quote source; `eastmoney` switches, the other becomes automatic backup |
| `BASE_CURRENCY` | `HKD` | base currency |
| `DATABASE_URL` | local SQLite | `postgresql+psycopg2://…` for Postgres |
| `CORS_ORIGINS` | `*` | frontend CORS |
| `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` | unset | when set, `/api/*` requires auth (except health) |
| `YFINANCE_TIMEOUT` | `15` | yfinance timeout, seconds |

### Deploy

```bash
docker compose up --build
```

## Disclaimer

Quotes are delayed and may be inaccurate. This tool is for personal bookkeeping only, not investment advice.

## License

MIT

## Buy me a coffee

If this project saved you some time, coffee is welcome. ☕

| Alipay | WeChat Pay |
| ------ | ---------- |
| ![Alipay QR](assets/alipay.jpg) | ![WeChat Pay QR](assets/wechat-pay.png) |
