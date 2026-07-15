import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload, load_only

from app.analysis.valuation import IMPLAUSIBLE_UPSIDE_PCT
from app.core.config import get_settings
from app.db.session import get_db
from app.jobs.live_quotes import is_market_open, market_session
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.schemas.analysis import (
    AnalysisHistoryPoint,
    AnalysisListItem,
    AnalysisRead,
    DashboardSummary,
    DistributionBucket,
    IdeaItem,
    IdeasResponse,
    MarketOverview,
    MoverItem,
    ScreenResponse,
)
from app.services.backtest import run_backtest
from app.services.discovery import build_radar
from app.services.market import sector_factor_matrix
from app.services.queries import (
    FACTOR_KEYS,
    eligible_conditions,
    latest_ids,
)
from app.services.screen_parser import parse_screen_query
from app.services.screener import list_analyses

router = APIRouter()


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
                StockAnalysis.upside_pct <= IMPLAUSIBLE_UPSIDE_PCT,
            )
        )
        or 0,
        last_analysis_at=db.scalar(select(func.max(StockAnalysis.as_of))),
        market_open=is_market_open(),
        market_session=market_session(),
        prices_updated_last_min=db.scalar(
            select(func.count())
            .select_from(StockAnalysis)
            .where(StockAnalysis.price_as_of >= datetime.now(UTC) - timedelta(minutes=1))
        )
        or 0,
        analyses_last_5min=db.scalar(
            select(func.count())
            .select_from(Company)
            .where(Company.analysis_attempted_at >= datetime.now(UTC) - timedelta(minutes=5))
        )
        or 0,
        newest_price_at=db.scalar(select(func.max(StockAnalysis.price_as_of))),
    )


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Annotated[Session, Depends(get_db)]) -> DashboardSummary:
    return build_summary(db)


@router.get("/backtest")
def rating_backtest(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Forward-return performance of each rating bucket, recomputed from the
    analyzer's own stored snapshot history. Research diagnostics — a measure of
    the rules' historical behavior, not a promise of future returns."""
    return run_backtest(db)


@router.get("/radar")
def discovery_radar(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Live market-wide radar: notable events (crosses, breakouts, unusual volume,
    movers, value setups) detected across every analyzed security right now."""
    return build_radar(db)


@router.get("/sector-factors")
def sector_factors(db: Annotated[Session, Depends(get_db)]) -> dict:
    """Average factor scores by sector — the market-structure heatmap."""
    return sector_factor_matrix(db)


@router.get("/list", response_model=list[AnalysisListItem])
def opportunities(
    db: Annotated[Session, Depends(get_db)],
    min_upside: Annotated[float, Query(ge=-100, le=10000)] = -100,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(gt=0)] = None,
    min_volume: Annotated[int | None, Query(ge=0)] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    signal: Literal["all", "Bullish", "Neutral", "Bearish"] = "all",
    golden_cross: bool = False,
    min_rsi: Annotated[float | None, Query(ge=0, le=100)] = None,
    max_rsi: Annotated[float | None, Query(ge=0, le=100)] = None,
    min_value: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_quality: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_momentum: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_growth: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_income: Annotated[int | None, Query(ge=0, le=100)] = None,
    watched_only: bool = False,
    search: Annotated[str | None, Query(max_length=100)] = None,
    sector: Annotated[str | None, Query(max_length=64)] = None,
    asset_type: Literal["all", "Stock", "ETF"] = "Stock",
    sort_by: Literal[
        "rating",
        "score",
        "upside",
        "name",
        "ticker",
        "price",
        "volume",
        "change_1d",
        "change_5d",
        "signal",
        "rsi",
        "confidence",
        "risk",
        "factor_composite",
        "factor_value",
        "factor_quality",
        "factor_momentum",
        "factor_growth",
        "factor_income",
    ] = "rating",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[StockAnalysis]:
    return list_analyses(
        db,
        min_upside=min_upside,
        min_price=min_price,
        max_price=max_price,
        min_volume=min_volume,
        min_score=min_score,
        signal=signal,
        golden_cross=golden_cross,
        min_rsi=min_rsi,
        max_rsi=max_rsi,
        min_value=min_value,
        min_quality=min_quality,
        min_momentum=min_momentum,
        min_growth=min_growth,
        min_income=min_income,
        watched_only=watched_only,
        search=search,
        sector=sector,
        asset_type=asset_type,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


@router.get("/screen", response_model=ScreenResponse)
def natural_screen(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
) -> ScreenResponse:
    """Plain-English screener: parse a natural-language request into structured
    filters (deterministically, no model) and return the matching securities plus
    a transparent list of how the request was interpreted."""
    parsed, interpretation = parse_screen_query(q)
    results = list_analyses(db, limit=limit, **parsed)
    return ScreenResponse(
        query=q,
        interpretation=interpretation,
        filters=parsed,
        count=len(results),
        results=results,
    )


@router.get("/sectors")
def sectors(
    db: Annotated[Session, Depends(get_db)],
    asset_type: Literal["all", "Stock", "ETF"] = "all",
) -> dict:
    """Analyzed-security counts grouped by sector, for the sector filter/grouping."""
    settings = get_settings()
    conditions = [StockAnalysis.id.in_(latest_ids()), *eligible_conditions(settings)]
    if asset_type != "all":
        conditions.append(Company.asset_type == asset_type)
    rows = db.execute(
        select(Company.sector, func.count())
        .join(StockAnalysis, StockAnalysis.company_id == Company.id)
        .where(*conditions)
        .group_by(Company.sector)
    ).all()
    groups = [
        {"sector": sector or "Unclassified", "count": count}
        for sector, count in rows
    ]
    groups.sort(key=lambda item: item["count"], reverse=True)
    return {"sectors": groups, "total": sum(item["count"] for item in groups)}


@router.get("/overview", response_model=MarketOverview)
def market_overview(db: Annotated[Session, Depends(get_db)]) -> MarketOverview:
    settings = get_settings()
    rows = db.execute(
        select(
            Company.ticker,
            Company.name,
            Company.asset_type,
            Company.exchange,
            Company.sector,
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
    sector_counts: Counter[str] = Counter()
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
        sector_counts[row.sector or "Unclassified"] += 1
        score_buckets[min(9, max(0, row.opportunity_score // 10))] += 1
        if row.asset_type == "Stock" and row.upside_pct <= IMPLAUSIBLE_UPSIDE_PCT:
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
        sector_counts=dict(sector_counts),
        top_gainers=sorted(with_change, key=lambda item: item.change_1d_pct, reverse=True)[:8],
        top_losers=sorted(with_change, key=lambda item: item.change_1d_pct)[:8],
        most_active=sorted(with_volume, key=lambda item: item.volume, reverse=True)[:8],
        highest_scores=sorted(movers, key=lambda item: item.opportunity_score, reverse=True)[:8],
    )


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


@router.get("/ideas", response_model=IdeasResponse)
def ideas(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> IdeasResponse:
    """Two transparent, rules-based idea lists — swing (momentum/liquidity) and
    long-term (quality fundamentals + long-term uptrend). Deterministic screens,
    not personalized investment advice."""
    settings = get_settings()
    rows = db.execute(
        select(
            Company.ticker,
            Company.name,
            Company.asset_type,
            StockAnalysis.current_price,
            StockAnalysis.upside_pct,
            StockAnalysis.opportunity_score,
            StockAnalysis.confidence_grade,
            StockAnalysis.risk_level,
            StockAnalysis.qualification,
            StockAnalysis.volume,
            StockAnalysis.net_income,
            StockAnalysis.free_cash_flow,
            StockAnalysis.revenue_growth_pct,
            StockAnalysis.technical_indicators,
            StockAnalysis.fundamentals,
        )
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(
            StockAnalysis.id.in_(latest_ids()),
            *eligible_conditions(settings),
            StockAnalysis.upside_pct <= IMPLAUSIBLE_UPSIDE_PCT,
        )
    ).all()

    swing: list[IdeaItem] = []
    long_term: list[IdeaItem] = []
    for row in rows:
        tech = row.technical_indicators or {}
        signal = tech.get("signal")
        rsi = _num(tech.get("rsi14"))
        conf = int(tech.get("confirmations") or 0)
        change_5d = _num(tech.get("change_5d_pct"))
        change_1d = _num(tech.get("change_1d_pct"))
        sma20 = _num(tech.get("sma20"))
        sma50 = _num(tech.get("sma50"))
        sma200 = _num(tech.get("sma200"))
        price = float(row.current_price)
        volume = row.volume or 0

        # ── Swing screen: momentum + liquidity, any asset type ──
        reasons: list[str] = []
        if (
            signal in {"Bullish", "Neutral"}
            and conf >= 4
            and volume >= 300_000
            and rsi is not None
            and 48 <= rsi <= 72
            and sma20 is not None
            and price > sma20
        ):
            score = conf * 12.0
            reasons.append(f"{conf}/6 trend checks pass")
            if sma50 is not None and price > sma50:
                score += 10
                reasons.append("Above SMA-20 & SMA-50")
            else:
                reasons.append("Above SMA-20")
            if change_5d is not None and change_5d > 0:
                score += min(change_5d, 15)
                reasons.append(f"+{change_5d:.1f}% over 5d")
            if 52 <= rsi <= 66:
                score += 8
            reasons.append(f"RSI {rsi:.0f}")
            if volume >= 2_000_000:
                score += 8
            reasons.append(f"{volume/1e6:.1f}M volume")
            if tech.get("trend_cross") == "Golden cross":
                score += 6
                reasons.append("Recent golden cross")
            swing.append(
                IdeaItem(
                    ticker=row.ticker, name=row.name, asset_type=row.asset_type,
                    current_price=row.current_price, change_1d_pct=change_1d,
                    change_5d_pct=change_5d, upside_pct=row.upside_pct,
                    opportunity_score=row.opportunity_score, signal=signal, rsi14=rsi,
                    confidence_grade=row.confidence_grade, risk_level=row.risk_level,
                    idea_score=round(score, 1), reasons=reasons[:5],
                )
            )

        # ── Long-term screen: quality fundamentals + long-term uptrend ──
        fundamentals = row.fundamentals or {}
        margins = fundamentals.get("margins") or {}
        cagr = _num(fundamentals.get("revenue_cagr_pct"))
        if (
            row.asset_type == "Stock"
            and row.qualification != "Technical Screen Only"
            and row.confidence_grade in {"A", "B"}
            and (row.free_cash_flow or 0) > 0
            and (row.net_income or 0) > 0
            and sma200 is not None
            and price > sma200
        ):
            lreasons: list[str] = [f"Confidence {row.confidence_grade}"]
            score = float(row.opportunity_score)
            score += 20 if row.confidence_grade == "A" else 10
            lreasons.append("Positive net income & free cash flow")
            score += 10
            lreasons.append("Price above SMA-200 (long uptrend)")
            score += 8
            if row.revenue_growth_pct and row.revenue_growth_pct > 5:
                score += min(row.revenue_growth_pct / 2, 12)
                lreasons.append(f"Revenue +{row.revenue_growth_pct:.0f}% YoY")
            if isinstance(cagr, float) and cagr > 8:
                score += 6
                lreasons.append(f"{cagr:.0f}% revenue CAGR")
            op_margin = _num(margins.get("operating_pct"))
            if op_margin is not None and op_margin >= 15:
                score += 6
                lreasons.append(f"{op_margin:.0f}% operating margin")
            if row.risk_level == "Low":
                score += 6
                lreasons.append("Low risk grade")
            long_term.append(
                IdeaItem(
                    ticker=row.ticker, name=row.name, asset_type=row.asset_type,
                    current_price=row.current_price, change_1d_pct=change_1d,
                    change_5d_pct=change_5d, upside_pct=row.upside_pct,
                    opportunity_score=row.opportunity_score, signal=signal, rsi14=rsi,
                    confidence_grade=row.confidence_grade, risk_level=row.risk_level,
                    idea_score=round(score, 1), reasons=lreasons[:5],
                )
            )

    swing.sort(key=lambda item: item.idea_score, reverse=True)
    long_term.sort(key=lambda item: item.idea_score, reverse=True)
    return IdeasResponse(swing=swing[:limit], long_term=long_term[:limit])


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



@router.get("/stocks/{ticker}/factors")
def stock_factors(ticker: str, db: Annotated[Session, Depends(get_db)]) -> dict:
    """Factor scores for a ticker plus its percentile rank within its own sector."""
    settings = get_settings()
    row = db.execute(
        select(StockAnalysis.factor_scores, Company.sector)
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(Company.ticker == ticker.upper())
        .order_by(StockAnalysis.as_of.desc())
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No analysis exists for this ticker")
    scores, sector = row
    scores = scores or {}

    peer_rows = db.execute(
        select(StockAnalysis.factor_scores)
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(
            StockAnalysis.id.in_(latest_ids()),
            *eligible_conditions(settings),
            Company.sector == sector,
        )
    ).all()
    peers = [item[0] or {} for item in peer_rows]

    percentiles: dict[str, int] = {}
    for key in FACTOR_KEYS:
        mine = scores.get(key)
        if not isinstance(mine, int | float):
            continue
        values = [p[key] for p in peers if isinstance(p.get(key), int | float)]
        if not values:
            continue
        rank = sum(1 for value in values if value <= mine)
        percentiles[key] = round(rank / len(values) * 100)

    return {
        "ticker": ticker.upper(),
        "sector": sector or "Unclassified",
        "peer_count": len(peers),
        "scores": {key: scores.get(key) for key in FACTOR_KEYS},
        "sector_percentiles": percentiles,
    }


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
