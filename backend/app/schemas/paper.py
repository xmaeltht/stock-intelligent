from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PaperPortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starting_cash: Decimal | None = Field(default=None, gt=0, le=100_000_000)
    max_risk_per_trade_pct: float | None = Field(default=None, gt=0, le=10)
    max_position_pct: float | None = Field(default=None, gt=0, le=100)


class PaperTradeCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    side: Literal["BUY", "SELL"]
    quantity: Decimal = Field(gt=0, le=100_000_000)
    price: Decimal | None = Field(default=None, gt=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    thesis: str | None = Field(default=None, max_length=2000)
    catalyst: str | None = Field(default=None, max_length=1000)
    invalidation_price: Decimal | None = Field(default=None, gt=0)
    target_price: Decimal | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=2000)


class RiskPlanCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    entry_price: Decimal | None = Field(default=None, gt=0)
    invalidation_price: Decimal = Field(gt=0)
    target_price: Decimal | None = Field(default=None, gt=0)
    risk_pct: float | None = Field(default=None, gt=0, le=10)


class RiskPlanRead(BaseModel):
    ticker: str
    portfolio_value: Decimal
    entry_price: Decimal
    invalidation_price: Decimal
    target_price: Decimal | None
    risk_pct: float
    risk_budget: Decimal
    risk_per_share: Decimal
    suggested_shares: Decimal
    suggested_position_value: Decimal
    position_pct: float
    reward_risk_ratio: float | None
    warnings: list[str]


class PaperTradeRead(BaseModel):
    id: str
    ticker: str
    name: str
    side: str
    quantity: Decimal
    price: Decimal
    fees: Decimal
    realized_pnl: Decimal | None
    thesis: str | None
    catalyst: str | None
    invalidation_price: Decimal | None
    target_price: Decimal | None
    notes: str | None
    executed_at: datetime


class PaperPositionRead(BaseModel):
    ticker: str
    name: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    unrealized_pct: float
    allocation_pct: float
    target_price: Decimal | None
    invalidation_price: Decimal | None


class PaperPortfolioRead(BaseModel):
    id: str
    name: str
    starting_cash: Decimal
    cash_balance: Decimal
    total_value: Decimal
    invested_value: Decimal
    total_return: Decimal
    total_return_pct: float
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    max_risk_per_trade_pct: float
    max_position_pct: float
    positions: list[PaperPositionRead]
    trades: list[PaperTradeRead]
