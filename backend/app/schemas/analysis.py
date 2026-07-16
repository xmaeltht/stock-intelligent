from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class CompanyBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    name: str
    exchange: str | None
    asset_type: str
    sector: str | None = None


class AnalysisListItem(BaseModel):
    """Lean row for tables: no price history or long-form evidence payloads."""

    model_config = ConfigDict(from_attributes=True)
    company: CompanyBrief
    as_of: datetime
    price_as_of: datetime | None = None
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
    factor_scores: dict[str, object] = {}

    @field_validator("technical_indicators", mode="before")
    @classmethod
    def compact_indicators(cls, value: object) -> dict[str, object]:
        """Keep table responses small; detail pages retain the full payload."""
        if not isinstance(value, dict):
            return {}
        keys = ("signal", "rsi14", "trend_cross", "change_1d_pct", "spark")
        return {key: value[key] for key in keys if key in value}


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    company: CompanyBrief
    as_of: datetime
    price_as_of: datetime | None = None
    price_date: date
    current_price: Decimal
    volume: int | None
    price_history: list[dict[str, object]]
    technical_indicators: dict[str, object]
    factor_scores: dict[str, object] = {}
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
    # Live-scan telemetry so the UI can show the analyzers are running non-stop.
    market_open: bool = False
    market_session: str = "closed"
    prices_updated_last_min: int = 0
    analyses_last_5min: int = 0
    newest_price_at: datetime | None = None


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
    sector_counts: dict[str, int]
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


class IdeaItem(BaseModel):
    ticker: str
    name: str
    asset_type: str
    current_price: Decimal
    change_1d_pct: float | None
    change_5d_pct: float | None
    upside_pct: float | None
    opportunity_score: int
    signal: str | None
    rsi14: float | None
    confidence_grade: str
    risk_level: str
    idea_score: float
    reasons: list[str]


class IdeasResponse(BaseModel):
    swing: list[IdeaItem]
    long_term: list[IdeaItem]


class ScreenResponse(BaseModel):
    query: str
    interpretation: list[dict[str, object]]
    filters: dict[str, object]
    count: int
    results: list[AnalysisListItem]
