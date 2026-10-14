"""Central configuration. Everything is overridable via environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()  # allow a local .env file to set the variables below

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SQLite by default for zero-setup dev; point at Postgres in production, e.g.
# postgresql+psycopg2://user:pass@db:5432/duetfolio
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'duetfolio.db')}")

# Portfolio base currency for valuation. Supported: HKD, USD, CNY
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "HKD").upper()

# yfinance network timeout (seconds)
YFINANCE_TIMEOUT = int(os.getenv("YFINANCE_TIMEOUT", "15"))

# Optional HTTP Basic auth for deployments: set BOTH to require credentials
# on every /api route except /api/health. Leave unset for local dev.
BASIC_AUTH_USER = os.getenv("BASIC_AUTH_USER", "")
BASIC_AUTH_PASS = os.getenv("BASIC_AUTH_PASS", "")

# Market data provider: "yfinance" (default, ~15min delayed) or "eastmoney"
# (unofficial push2 API). Whichever is primary, the other serves as automatic
# per-symbol fallback when the primary returns nothing.
# yfinance: zero-setup and reliable. eastmoney: closer to real-time for CN
# investors, but unofficial, may break without notice, and lacks some fields.
MARKET_PROVIDER = os.getenv("MARKET_PROVIDER", "yfinance").lower()

# CORS: comma-separated origins. "*" (default) is convenient for local dev;
# an empty string disables CORS entirely (same-origin only), which is what
# the Docker image uses since nginx serves UI and API on one origin.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Default cost-basis method: "wac" (weighted average, like most HK/CN broker
# apps) or "fifo" (first-in-first-out, like most US brokers). The UI can
# override it per request with ?method=.
COST_METHOD = os.getenv("COST_METHOD", "wac").lower()
if COST_METHOD not in ("wac", "fifo"):
    COST_METHOD = "wac"

# Quotes fetched less than this many seconds ago are not re-fetched on
# refresh (persisted via price_snapshots.fetched_at). 0 disables the TTL.
QUOTE_TTL_SECONDS = int(os.getenv("QUOTE_TTL_SECONDS", "300"))

# Public read-only demo: seeds a showcase portfolio into an empty DB and
# rejects writes. See app/demo.py.
DEMO_MODE = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")
