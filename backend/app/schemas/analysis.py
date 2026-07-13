from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompanyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    name: str
    exchange: str | None
    asset_type: str


class AnalysisListItem(BaseModel):
    """Lean row for tables: no price history or long-form evidence payloads."""

    model_config = ConfigDict(from_attributes=True)
    company: CompanyBrief
    as_of: datetime
    price_date: date
    current_price: Decimal
    volume: int | None
    fair_value: Decimal
    upside_pct: float
    opportunity_score: int
    confidence_grade: str
    risk_level: str
    qualification: str
    technical_indicators: dict[str, object]
    catalysts: list[dict[str, object]]


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    company: CompanyBrief
    as_of: datetime
    price_date: date
    current_price: Decimal
    volume: int | None
    price_history: list[dict[str, object]]
    technical_indicators: dict[str, object]
    revenue: Decimal | None
    revenue_growth_pct: float | None
    net_income: Decimal | None
    free_cash_flow: Decimal | None
    cash: Decimal | None
    debt: Decimal | None
    fair_value: Decimal
    bear_value: Decimal
    bull_value: Decimal
    upside_pct: float
    opportunity_score: int
    confidence_grade: str
    risk_level: str
    qualification: str
    valuation_methods: list[dict[str, object]]
    fundamentals: dict[str, object]
    catalysts: list[dict[str, object]]
    risks: list[dict[str, object]]
    thesis_breakers: list[str]
    sources: list[dict[str, str]]


class AnalysisHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: datetime
    price_date: date
    current_price: Decimal
    fair_value: Decimal
    upside_pct: float
    opportunity_score: int
    confidence_grade: str


class DashboardSummary(BaseModel):
    company_count: int
    eligible_count: int
    analysis_count: int
    attempted_count: int
    failed_count: int
    remaining_count: int
    coverage_pct: float
    qualified_count: int
    last_analysis_at: datetime | None


class MoverItem(BaseModel):
    ticker: str
    name: str
    asset_type: str
    current_price: Decimal
    change_1d_pct: float | None
    upside_pct: float
    opportunity_score: int
    signal: str | None
    volume: int | None


class DistributionBucket(BaseModel):
    label: str
    count: int


class MarketOverview(BaseModel):
    summary: DashboardSummary
    signal_breadth: dict[str, int]
    impulse_breadth: dict[str, int]
    score_distribution: list[DistributionBucket]
    upside_distribution: list[DistributionBucket]
    exchange_counts: dict[str, int]
    asset_type_counts: dict[str, int]
    top_gainers: list[MoverItem]
    top_losers: list[MoverItem]
    most_active: list[MoverItem]
    highest_scores: list[MoverItem]


class WatchlistItem(BaseModel):
    ticker: str
    name: str
    exchange: str | None
    asset_type: str
    note: str | None
    created_at: datetime
    latest: AnalysisListItem | None
