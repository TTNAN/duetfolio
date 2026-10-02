"""Pydantic v2 request/response schemas."""
from datetime import date, datetime
from datetime import date as date_cls  # alias: TransactionUpdate.date shadows `date`
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class InstrumentCreate(BaseModel):
    symbol: str = Field(..., examples=["SGOV", "03152.HK"], description="Yahoo Finance ticker")
    name: str = ""
    market: Literal["US", "HK"] = "US"
    currency: Literal["USD", "HKD"] = "USD"
    asset_type: Literal["stock", "etf", "fund"] = "etf"


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    name: str
    market: str
    currency: str
    asset_type: str
    created_at: datetime


class TransactionCreate(BaseModel):
    instrument_id: int
    type: Literal["buy", "sell", "dividend"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., ge=0, description="Per-share price in instrument currency")
    fee: float = 0.0
    date: date
    note: str = ""


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    instrument_id: int
    type: str
    quantity: float
    price: float
    fee: float
    date: date
    note: str
    fx_to_hkd: Optional[float] = None  # rate captured on the transaction date
    symbol: Optional[str] = None  # joined for display


class TransactionUpdate(BaseModel):
    """Inline edit: every field optional. fx_to_hkd is KEPT unless
    refetch_fx is set — then it's re-fetched for the (possibly new) date."""
    type: Optional[Literal["buy", "sell", "dividend"]] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    price: Optional[float] = Field(default=None, ge=0)
    fee: Optional[float] = Field(default=None, ge=0)
    date: Optional[date_cls] = None
    note: Optional[str] = None
    refetch_fx: bool = False


class HoldingOut(BaseModel):
    instrument_id: int
    symbol: str
    name: str
    market: str
    currency: str
    quantity: float
    avg_cost: float
    invested: float          # in instrument currency (remaining cost basis)
    realized_pnl: float = 0.0  # in instrument currency, sells & dividends net of fees
    latest_price: Optional[float] = None
    price_date: Optional[date] = None
    market_value: Optional[float] = None   # in instrument currency
    unrealized_pnl: Optional[float] = None
    # converted to base currency
    market_value_base: Optional[float] = None
    unrealized_pnl_base: Optional[float] = None
    # day change (needs prev_close from the last refresh)
    prev_close: Optional[float] = None       # in instrument currency
    day_change: Optional[float] = None       # close - prev_close, instrument ccy
    day_change_pct: Optional[float] = None   # e.g. 0.012 = +1.2%
    day_change_base: Optional[float] = None  # day P&L on the position, base ccy
    weight_pct: Optional[float] = None       # share of total_value, e.g. 23.2


class PortfolioSummary(BaseModel):
    base_currency: str
    fx_usd_to_base: Optional[float] = None
    total_value: Optional[float] = None
    total_invested: Optional[float] = None  # remaining cost basis (not cumulative)
    total_pnl: Optional[float] = None       # cumulative: unrealized + realized
    unrealized_pnl: Optional[float] = None  # market value - remaining cost
    realized_pnl: Optional[float] = None    # sells & dividends, net of fees
    xirr: Optional[float] = None  # annualized, e.g. 0.083 = 8.3%
    holdings: list[HoldingOut]
    price_stale: list[str] = []   # symbols without a fresh price
    fx_stale: list[str] = []      # currencies without a convertible FX rate
    quotes_as_of: Optional[datetime] = None  # when quotes were last fetched
    quotes_source: Optional[str] = None      # provider name, e.g. yfinance
    dividends_12m: Optional[float] = None    # dividends, trailing 12 months, base ccy


class HistoryPoint(BaseModel):
    date: date
    value: Optional[float] = None  # None when FX gaps make this day unconvertible


class InstrumentCandidate(BaseModel):
    """One hit from the symbol search box (Yahoo / East Money suggest)."""
    symbol: str       # Yahoo-format ticker, e.g. "3152.HK", "SGOV"
    name: str
    market: Literal["US", "HK"]
    currency: str     # "USD" | "HKD"
    source: str       # "yahoo" | "eastmoney"


class CashFlowCreate(BaseModel):
    date: date_cls
    direction: Literal["in", "out"]  # in = deposit, out = withdrawal
    amount: float = Field(..., gt=0)
    currency: str = "HKD"
    note: str = ""


class CashFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date_cls
    direction: str
    amount: float
    currency: str
    note: str
