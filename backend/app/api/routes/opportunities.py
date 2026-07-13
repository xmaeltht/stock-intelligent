import re
from collections import Counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, aliased, joinedload, load_only

from app.core.config import get_settings
from app.db.session import get_db
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.schemas.analysis import (
    AnalysisHistoryPoint,
    AnalysisListItem,
    AnalysisRead,
    DashboardSummary,
    DistributionBucket,
    MarketOverview,
    MoverItem,
)

router = APIRouter()

LIST_COLUMNS = (
    StockAnalysis.company_id,
    StockAnalysis.as_of,
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
    StockAnalysis.catalysts,
)


def latest_ids():
    prior = aliased(StockAnalysis)
    latest_time = (
        select(func.max(prior.as_of))
        .where(prior.company_id == StockAnalysis.company_id)
        .correlate(StockAnalysis)
        .scalar_subquery()
    )
    return select(StockAnalysis.id).where(StockAnalysis.as_of == latest_time)


def eligible_conditions(settings):
    return (
        Company.is_active.is_(True),
        Company.is_research_eligible.is_(True),
        or_(Company.cik.is_not(None), Company.asset_type == "ETF"),
        Company.exchange.in_(settings.exchange_list),
    )


def build_summary(db: Session) -> DashboardSummary:
    settings = get_settings()
    ids = latest_ids()
    eligible = eligible_conditions(settings)
    eligible_count = db.scalar(
        select(func.count()).select_from(Company).where(*eligible)
    ) or 0
    analysis_count = db.scalar(
        select(func.count())
        .select_from(StockAnalysis)
        .join(Company)
        .where(StockAnalysis.id.in_(ids), *eligible)
    ) or 0
    attempted_count = db.scalar(
        select(func.count())
        .select_from(Company)
        .where(*eligible, Company.analysis_attempted_at.is_not(None))
    ) or 0
    failed_count = db.scalar(
        select(func.count())
        .select_from(Company)
        .where(*eligible, Company.analysis_error.is_not(None))
    ) or 0
    return DashboardSummary(
        company_count=db.scalar(select(func.count()).select_from(Company)) or 0,
        eligible_count=eligible_count,
        analysis_count=analysis_count,
        attempted_count=attempted_count,
        failed_count=failed_count,
        remaining_count=max(eligible_count - analysis_count, 0),
        coverage_pct=round((analysis_count / eligible_count * 100) if eligible_count else 0, 1),
        qualified_count=db.scalar(
            select(func.count())
            .select_from(StockAnalysis)
            .join(Company)
            .where(
                StockAnalysis.id.in_(ids),
                *eligible,
                Company.asset_type == "Stock",
                StockAnalysis.upside_pct >= 90,
            )
        )
        or 0,
        last_analysis_at=db.scalar(select(func.max(StockAnalysis.as_of))),
    )


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Annotated[Session, Depends(get_db)]) -> DashboardSummary:
    return build_summary(db)


@router.get("/list", response_model=list[AnalysisListItem])
def opportunities(
    db: Annotated[Session, Depends(get_db)],
    min_upside: Annotated[float, Query(ge=-100, le=10000)] = -100,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(gt=0)] = None,
    min_volume: Annotated[int | None, Query(ge=0)] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    signal: Literal["all", "Bullish", "Neutral", "Bearish"] = "all",
    watched_only: bool = False,
    search: Annotated[str | None, Query(max_length=100)] = None,
    asset_type: Literal["all", "Stock", "ETF"] = "Stock",
    sort_by: Literal["score", "upside", "name", "ticker", "price", "volume"] = "score",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[StockAnalysis]:
    # A ticker/company search should always surface the match, even for
    # technical-screen names whose modeled upside is 0 and would otherwise be
    # hidden by the upside threshold.
    effective_min_upside = -100.0 if search else min_upside
    filters = [
        StockAnalysis.id.in_(latest_ids()),
        Company.is_research_eligible.is_(True),
        StockAnalysis.upside_pct >= effective_min_upside,
    ]
    if asset_type != "all":
        filters.append(Company.asset_type == asset_type)
    if min_price is not None:
        filters.append(StockAnalysis.current_price >= min_price)
    if max_price is not None:
        filters.append(StockAnalysis.current_price <= max_price)
    if min_volume is not None:
        filters.append(StockAnalysis.volume >= min_volume)
    if min_score is not None:
        filters.append(StockAnalysis.opportunity_score >= min_score)
    if signal != "all":
        filters.append(
            StockAnalysis.technical_indicators["signal"].as_string() == signal
        )
    if watched_only:
        from app.models.watchlist import WatchlistEntry

        filters.append(
            StockAnalysis.company_id.in_(select(WatchlistEntry.company_id))
        )
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(Company.ticker.ilike(pattern) | Company.name.ilike(pattern))

    sort_columns = {
        "score": StockAnalysis.opportunity_score,
        "upside": StockAnalysis.upside_pct,
        "name": Company.name,
        "ticker": Company.ticker,
        "price": StockAnalysis.current_price,
        "volume": StockAnalysis.volume,
    }
    sort_column = sort_columns[sort_by]
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


@router.get("/overview", response_model=MarketOverview)
def market_overview(db: Annotated[Session, Depends(get_db)]) -> MarketOverview:
    settings = get_settings()
    rows = db.execute(
        select(
            Company.ticker,
            Company.name,
            Company.asset_type,
            Company.exchange,
            StockAnalysis.current_price,
            StockAnalysis.upside_pct,
            StockAnalysis.opportunity_score,
            StockAnalysis.volume,
            StockAnalysis.technical_indicators,
        )
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(
            StockAnalysis.id.in_(latest_ids()),
            *eligible_conditions(settings),
        )
    ).all()

    signal_breadth: Counter[str] = Counter()
    impulse_breadth: Counter[str] = Counter()
    exchange_counts: Counter[str] = Counter()
    asset_type_counts: Counter[str] = Counter()
    score_buckets = [0] * 10
    upside_labels = ["Below 0%", "0-50%", "50-100%", "100-200%", "200%+"]
    upside_buckets = [0] * len(upside_labels)
    movers: list[MoverItem] = []

    for row in rows:
        indicators = row.technical_indicators or {}
        signal_breadth[str(indicators.get("signal") or "Pending")] += 1
        impulse_breadth[str(indicators.get("impulse_macd") or "Pending")] += 1
        exchange_counts[row.exchange or "Unknown"] += 1
        asset_type_counts[row.asset_type] += 1
        score_buckets[min(9, max(0, row.opportunity_score // 10))] += 1
        if row.asset_type == "Stock":
            upside = row.upside_pct
            index = (
                0 if upside < 0
                else 1 if upside < 50
                else 2 if upside < 100
                else 3 if upside < 200
                else 4
            )
            upside_buckets[index] += 1
        change = indicators.get("change_1d_pct")
        movers.append(
            MoverItem(
                ticker=row.ticker,
                name=row.name,
                asset_type=row.asset_type,
                current_price=row.current_price,
                change_1d_pct=change if isinstance(change, int | float) else None,
                upside_pct=row.upside_pct,
                opportunity_score=row.opportunity_score,
                signal=str(indicators.get("signal")) if indicators.get("signal") else None,
                volume=row.volume,
            )
        )

    with_change = [item for item in movers if item.change_1d_pct is not None]
    with_volume = [item for item in movers if item.volume is not None]
    return MarketOverview(
        summary=build_summary(db),
        signal_breadth=dict(signal_breadth),
        impulse_breadth=dict(impulse_breadth),
        score_distribution=[
            DistributionBucket(label=f"{index * 10}-{index * 10 + 9}", count=count)
            for index, count in enumerate(score_buckets)
        ],
        upside_distribution=[
            DistributionBucket(label=label, count=count)
            for label, count in zip(upside_labels, upside_buckets, strict=True)
        ],
        exchange_counts=dict(exchange_counts),
        asset_type_counts=dict(asset_type_counts),
        top_gainers=sorted(with_change, key=lambda item: item.change_1d_pct, reverse=True)[:8],
        top_losers=sorted(with_change, key=lambda item: item.change_1d_pct)[:8],
        most_active=sorted(with_volume, key=lambda item: item.volume, reverse=True)[:8],
        highest_scores=sorted(movers, key=lambda item: item.opportunity_score, reverse=True)[:8],
    )


@router.get("/compare", response_model=list[AnalysisRead])
def compare(
    db: Annotated[Session, Depends(get_db)],
    tickers: Annotated[str, Query(min_length=1, max_length=120)],
) -> list[StockAnalysis]:
    requested = [item.strip().upper() for item in tickers.split(",") if item.strip()][:6]
    if not requested:
        raise HTTPException(status_code=422, detail="Provide at least one ticker")
    results: list[StockAnalysis] = []
    for ticker in requested:
        analysis = db.scalar(
            select(StockAnalysis)
            .join(StockAnalysis.company)
            .options(joinedload(StockAnalysis.company))
            .where(Company.ticker == ticker)
            .order_by(StockAnalysis.as_of.desc())
            .limit(1)
        )
        if analysis is not None:
            results.append(analysis)
    return results


@router.get("/failures")
def failure_summary(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict:
    """Group stored per-company analysis errors so the failed queue is explainable."""
    rows = db.execute(
        select(Company.ticker, Company.exchange, Company.asset_type, Company.analysis_error)
        .where(Company.analysis_error.is_not(None))
    ).all()
    groups: dict[str, dict] = {}
    for ticker, exchange, asset_type, error in rows:
        normalized = re.sub(r"\bfor [A-Z0-9.\-+]{1,10}\b", "for <ticker>", error)
        normalized = re.sub(r"\b[A-Z0-9.\-+]{1,10} is absent\b", "<ticker> is absent", normalized)
        normalized = re.sub(r"CIK\d+", "CIK<n>", normalized)[:200]
        group = groups.setdefault(
            normalized,
            {
                "error": normalized,
                "count": 0,
                "examples": [],
                "exchanges": Counter(),
                "asset_types": Counter(),
            },
        )
        group["count"] += 1
        if len(group["examples"]) < 5:
            group["examples"].append(ticker)
        group["exchanges"][exchange or "Unknown"] += 1
        group["asset_types"][asset_type] += 1
    ordered = sorted(groups.values(), key=lambda item: item["count"], reverse=True)[:limit]
    return {
        "total_failed": len(rows),
        "distinct_errors": len(groups),
        "top_errors": [
            {
                "error": item["error"],
                "count": item["count"],
                "examples": item["examples"],
                "exchanges": dict(item["exchanges"].most_common(5)),
                "asset_types": dict(item["asset_types"]),
            }
            for item in ordered
        ],
    }


@router.post("/requeue-failures")
def requeue_failures(
    db: Annotated[Session, Depends(get_db)],
    scope: Literal["failures", "stale", "all"] = "failures",
) -> dict:
    """Clear analyzer cooldowns so the continuous analyzer reprocesses now.

    scope=failures: only securities whose last attempt errored (default).
    scope=stale: failures plus securities whose latest stored analysis predates
    the market-data pipeline (no volume/chart/indicators recorded).
    scope=all: every company.
    """
    if scope == "failures":
        condition = Company.analysis_error.is_not(None)
    elif scope == "stale":
        stale_companies = select(StockAnalysis.company_id).where(
            StockAnalysis.id.in_(latest_ids()),
            StockAnalysis.volume.is_(None),
        )
        condition = or_(
            Company.analysis_error.is_not(None),
            Company.id.in_(stale_companies),
        )
    else:
        condition = Company.id.is_not(None)
    result = db.execute(
        update(Company)
        .where(condition)
        .values(analysis_error=None, analysis_attempted_at=None)
    )
    db.commit()
    return {"scope": scope, "requeued": result.rowcount}


@router.get("/stocks/{ticker}", response_model=AnalysisRead)
def stock_detail(ticker: str, db: Annotated[Session, Depends(get_db)]) -> StockAnalysis:
    statement = (
        select(StockAnalysis)
        .join(StockAnalysis.company)
        .options(joinedload(StockAnalysis.company))
        .where(Company.ticker == ticker.upper())
        .order_by(StockAnalysis.as_of.desc())
        .limit(1)
    )
    analysis = db.scalar(statement)
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis exists for this ticker")
    return analysis


@router.get("/stocks/{ticker}/history", response_model=list[AnalysisHistoryPoint])
def stock_history(
    ticker: str,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=365)] = 120,
) -> list[StockAnalysis]:
    rows = list(
        db.scalars(
            select(StockAnalysis)
            .join(StockAnalysis.company)
            .options(
                load_only(
                    StockAnalysis.as_of,
                    StockAnalysis.price_date,
                    StockAnalysis.current_price,
                    StockAnalysis.fair_value,
                    StockAnalysis.upside_pct,
                    StockAnalysis.opportunity_score,
                    StockAnalysis.confidence_grade,
                )
            )
            .where(Company.ticker == ticker.upper())
            .order_by(StockAnalysis.as_of.desc())
            .limit(limit)
        )
    )
    rows.reverse()
    return rows
