"""Shared query primitives for the research API and services.

Single source of truth for "the latest analysis per company", the eligibility
predicate, and the rules-based rating expression — previously duplicated across
the route module and each service.
"""

from sqlalchemy import case, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func

from app.models.company import Company
from app.models.stock_analysis import StockAnalysis

FACTOR_KEYS = ("value", "quality", "momentum", "growth", "income", "composite")


def latest_ids():
    """Subquery selecting the id of the most recent analysis for each company."""
    prior = aliased(StockAnalysis)
    latest_time = (
        select(func.max(prior.as_of))
        .where(prior.company_id == StockAnalysis.company_id)
        .correlate(StockAnalysis)
        .scalar_subquery()
    )
    return select(StockAnalysis.id).where(StockAnalysis.as_of == latest_time)


def eligible_conditions(settings):
    """Predicate tuple for research-eligible, actively-listed securities."""
    return (
        Company.is_active.is_(True),
        Company.is_research_eligible.is_(True),
        or_(Company.cik.is_not(None), Company.asset_type == "ETF"),
        Company.exchange.in_(settings.exchange_list),
    )


def clamp_expr(expr, low: float, high: float):
    """Portable numeric clamp (SQLite has no scalar greatest/least)."""
    return case((expr < low, low), (expr > high, high), else_=expr)


def rating_expression():
    """Numeric composite mirroring the rules-based rating, so the whole universe
    can be ranked Strong Buy → Sell in SQL. Higher is more bullish."""
    indicators = StockAnalysis.technical_indicators
    signal = indicators["signal"].as_string()
    rsi = indicators["rsi14"].as_float()
    cross = indicators["trend_cross"].as_string()
    signal_term = case((signal == "Bullish", 2.0), (signal == "Bearish", -2.0), else_=0.0)
    upside_term = case(
        (
            (Company.asset_type == "Stock")
            & (StockAnalysis.qualification != "Technical Screen Only"),
            clamp_expr(StockAnalysis.upside_pct / 20.0, -3.0, 4.0),
        ),
        else_=0.0,
    )
    cross_term = case((cross == "Golden cross", 1.0), (cross == "Death cross", -1.0), else_=0.0)
    rsi_term = case(
        (rsi >= 78, -1.0),
        (rsi <= 30, 1.0),
        ((rsi >= 45) & (rsi <= 68), 0.5),
        else_=0.0,
    )
    risk_term = case(
        (StockAnalysis.risk_level == "Low", 0.5),
        (StockAnalysis.risk_level == "High", -0.5),
        else_=0.0,
    )
    score_term = clamp_expr((StockAnalysis.opportunity_score - 50) / 25.0, -2.0, 2.0)
    return signal_term + upside_term + cross_term + rsi_term + risk_term + score_term
