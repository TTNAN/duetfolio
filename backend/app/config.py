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

# CORS: comma-separated origins, "*" for dev
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
