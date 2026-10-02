[简体中文](README.md) | **English**

# duetfolio ◈

A dual-market (US + HK) portfolio tracker — one home-currency number for holdings across both markets.

## Why

Most portfolio trackers are US/EU-centric. If your holdings span US and Hong Kong markets in two currencies, you end up converting in your head. duetfolio pulls both markets via Yahoo Finance, converts everything to your base currency (HKD/USD/CNY), and shows true annualized return (XIRR) including dividends.

## Features

- 📈 **Dual-market prices** — US tickers as-is (`SGOV`), HK tickers with `.HK` suffix (`3152.HK`), via Yahoo Finance
- 💱 **Multi-currency valuation** — every holding converted to your base currency with live FX (`HKD=X`)
- 🧮 **XIRR** — true annualized return from actual cash flows (buys, sells, dividends + terminal value), pure-Python implementation
- 🧾 **Transactions as source of truth** — holdings are always derived, never stored; average-cost basis
- 🐳 **One-command deploy** — `docker compose up`

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (async-ready), Alembic, Pydantic v2 |
| Database | SQLite (dev) / PostgreSQL (prod, via `DATABASE_URL`) |
| Market data | yfinance (Yahoo Finance) |
| Frontend | React 18 + Vite, hand-rolled SVG charts (zero chart deps) |
| Deploy | Docker Compose |

## Quick start

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # Alembic migrations run automatically on startup
# API docs: http://localhost:8000/docs
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api to :8000)
```

**Docker:**
```bash
docker compose up --build
# web: http://localhost:5173  api: http://localhost:8000/docs
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET/POST | `/api/instruments` | List / create instruments |
| DELETE | `/api/instruments/{id}` | Delete (+ all its transactions) |
| GET/POST | `/api/transactions` | List / record buy, sell, dividend |
| DELETE | `/api/transactions/{id}` | Delete |
| GET | `/api/portfolio/summary?base=HKD` | Valuation, P&L, XIRR, holdings |
| POST | `/api/prices/refresh` | Pull latest closes from Yahoo Finance |

## Scope decisions (deliberate)

- **Single user, no auth** — auth is the next milestone, not this one.
- **SQLite default** — zero-setup dev; `DATABASE_URL` switches to Postgres untouched.
- **Average-cost basis** — simple, auditable; FIFO is a future option.
- **Prices are a cache** — `price_snapshots` is a resilience layer, not canonical state.
- **Yahoo HK tickers drop the leading zero** — e.g. 03152 (Bosera HKD Money Market ETF) is `3152.HK` on Yahoo, not `03152.HK`. Some small HK money-market ETFs aren't covered by Yahoo at all.
- **XIRR annualizes aggressively** — a 4-day holding period produces extreme annualized numbers; that's the math, not a bug. XIRR is only reported when every holding has a fresh price.

## Disclaimer

Yahoo Finance data is delayed (~15 min) and may be inaccurate. This is a personal tracking tool, not investment advice.

## License

MIT

## Buy me a coffee

If this project saved you some time, consider buying me a coffee. ☕

| Alipay | WeChat Pay |
| ------ | ---------- |
| ![Alipay QR code](assets/alipay.jpg) | ![WeChat Pay QR code](assets/wechat-pay.png) |
