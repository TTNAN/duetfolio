"""Central configuration. Everything is overridable via environment variables."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SQLite by default for zero-setup dev; point at Postgres in production, e.g.
# postgresql+psycopg2://user:pass@db:5432/duetfolio
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'duetfolio.db')}")

# Portfolio base currency for valuation. Supported: HKD, USD, CNY
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "HKD").upper()

# yfinance network timeout (seconds)
YFINANCE_TIMEOUT = int(os.getenv("YFINANCE_TIMEOUT", "15"))

# CORS: comma-separated origins, "*" for dev
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
