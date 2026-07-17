"""Screener query service.

The single place that turns filter parameters into ranked analysis rows. Shared
by the guided `/list` endpoint and the natural-language `/screen` endpoint so the
filtering and ranking behaviour is identical for both.
"""

from sqlalchemy import case, select
from sqlalchemy.orm import Session, joinedload, load_only

from app.analysis.valuation import IMPLAUSIBLE_UPSIDE_PCT
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.services.queries import latest_ids, rating_expression

# Lean projection for table rows — no price history or long-form evidence.
LIST_COLUMNS = (
    StockAnalysis.company_id,
    StockAnalysis.as_of,
    StockAnalysis.price_as_of,
    StockAnalysis.price_date,
    StockAnalysis.current_price,
    StockAnalysis.volume,
    StockAnalysis.fair_value,
    StockAnalysis.upside_pct,
    StockAnalysis.opportunity_score,
    StockAnalysis.confidence_grade,
    StockAnalysis.risk_level,
    StockAnalysis.qualification,
    StockAnalysis.technical_indicators,
    StockAnalysis.factor_scores,
)


def _sort_columns():
    indicators = StockAnalysis.technical_indicators
    signal_rank = case(
        (indicators["signal"].as_string() == "Bullish", 3),
        (indicators["signal"].as_string() == "Neutral", 2),
        (indicators["signal"].as_string() == "Bearish", 1),
        else_=0,
    )
    confidence_rank = case(
        (StockAnalysis.confidence_grade == "A", 4),
        (StockAnalysis.confidence_grade == "B", 3),
        (StockAnalysis.confidence_grade == "C", 2),
        (StockAnalysis.confidence_grade == "D", 1),
        else_=0,
    )
    risk_rank = case(
        (StockAnalysis.risk_level == "Low", 3),
        (StockAnalysis.risk_level == "Moderate", 2),
        (StockAnalysis.risk_level == "High", 1),
        else_=0,
    )
    return {
        "rating": rating_expression(),
        "score": StockAnalysis.opportunity_score,
        "upside": StockAnalysis.upside_pct,
        "name": Company.name,
        "ticker": Company.ticker,
        "price": StockAnalysis.current_price,
        "volume": StockAnalysis.volume,
        "change_1d": indicators["change_1d_pct"].as_float(),
        "change_5d": indicators["change_5d_pct"].as_float(),
        "signal": signal_rank,
        "rsi": indicators["rsi14"].as_float(),
        "confidence": confidence_rank,
        "risk": risk_rank,
        "factor_composite": StockAnalysis.factor_scores["composite"].as_float(),
        "factor_value": StockAnalysis.factor_scores["value"].as_float(),
        "factor_quality": StockAnalysis.factor_scores["quality"].as_float(),
        "factor_momentum": StockAnalysis.factor_scores["momentum"].as_float(),
        "factor_growth": StockAnalysis.factor_scores["growth"].as_float(),
        "factor_income": StockAnalysis.factor_scores["income"].as_float(),
    }


def list_analyses(
    db: Session,
    *,
    min_upside: float = -100,
    min_price: float | None = None,
    max_price: float | None = None,
    min_volume: int | None = None,
    min_score: int | None = None,
    signal: str = "all",
    golden_cross: bool = False,
    min_rsi: float | None = None,
    max_rsi: float | None = None,
    min_value: int | None = None,
    min_quality: int | None = None,
    min_momentum: int | None = None,
    min_growth: int | None = None,
    min_income: int | None = None,
    watched_only: bool = False,
    watched_user_id=None,
    search: str | None = None,
    sector: str | None = None,
    asset_type: str = "Stock",
    sort_by: str = "rating",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> list[StockAnalysis]:
    # A ticker/company search should always surface the match, regardless of the
    # upside threshold or the Stocks/ETFs toggle — otherwise a searched symbol
    # (e.g. a leveraged ETF while "Stocks" is selected) silently returns nothing.
    effective_min_upside = -100.0 if search else min_upside
    filters = [
        StockAnalysis.id.in_(latest_ids()),
        Company.is_research_eligible.is_(True),
        StockAnalysis.upside_pct >= effective_min_upside,
    ]
    if not search:
        filters.append(StockAnalysis.upside_pct <= IMPLAUSIBLE_UPSIDE_PCT)
    if asset_type != "all" and not search:
        filters.append(Company.asset_type == asset_type)
    if sector and not search:
        filters.append(Company.sector == sector)
    if min_price is not None:
        filters.append(StockAnalysis.current_price >= min_price)
    if max_price is not None:
        filters.append(StockAnalysis.current_price <= max_price)
    if min_volume is not None:
        filters.append(StockAnalysis.volume >= min_volume)
    if min_score is not None:
        filters.append(StockAnalysis.opportunity_score >= min_score)
    if signal != "all":
        filters.append(StockAnalysis.technical_indicators["signal"].as_string() == signal)
    if golden_cross:
        filters.append(
            StockAnalysis.technical_indicators["trend_cross"].as_string() == "Golden cross"
        )
    if min_rsi is not None:
        filters.append(StockAnalysis.technical_indicators["rsi14"].as_float() >= min_rsi)
    if max_rsi is not None:
        filters.append(StockAnalysis.technical_indicators["rsi14"].as_float() <= max_rsi)
    for key, threshold in (
        ("value", min_value),
        ("quality", min_quality),
        ("momentum", min_momentum),
        ("growth", min_growth),
        ("income", min_income),
    ):
        if threshold is not None:
            filters.append(StockAnalysis.factor_scores[key].as_float() >= threshold)
    if watched_only:
        from app.models.watchlist import WatchlistEntry

        if watched_user_id is None:
            # Anonymous visitors have no watchlist — return nothing rather than
            # leaking every user's starred tickers.
            filters.append(StockAnalysis.id.is_(None))
        else:
            filters.append(
                StockAnalysis.company_id.in_(
                    select(WatchlistEntry.company_id).where(
                        WatchlistEntry.user_id == watched_user_id
                    )
                )
            )
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(Company.ticker.ilike(pattern) | Company.name.ilike(pattern))

    sort_column = _sort_columns()[sort_by]
    ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    statement = (
        select(StockAnalysis)
        .join(Company)
        .options(load_only(*LIST_COLUMNS), joinedload(StockAnalysis.company))
        .where(*filters)
        .order_by(ordering.nulls_last(), StockAnalysis.opportunity_score.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement))
