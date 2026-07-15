"""Rating backtest: measure the forward return of each rating bucket from the
analyzer's own stored history.

For every historical analysis snapshot we recompute the rating it implied at the
time, then look up the security's actual return over 1/3/6-month horizons using
that security's daily price series. Aggregated by rating, this answers the
question competitors hide: do the ratings actually work?
"""

from bisect import bisect_right
from statistics import fmean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.rating import RATING_ORDER, derive_rating
from app.core.config import get_settings
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.services.queries import eligible_conditions, latest_ids

HORIZONS = ((21, "1M"), (63, "3M"), (126, "6M"))
MAX_OBSERVATIONS = 250_000


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _summarize(returns: list[float]) -> dict:
    if not returns:
        return {"n": 0, "avg_return_pct": None, "median_return_pct": None, "hit_rate_pct": None}
    wins = sum(1 for r in returns if r > 0)
    return {
        "n": len(returns),
        "avg_return_pct": round(fmean(returns) * 100, 2),
        "median_return_pct": round(median(returns) * 100, 2),
        "hit_rate_pct": round(wins / len(returns) * 100, 1),
    }


def run_backtest(db: Session) -> dict:
    settings = get_settings()
    eligible = eligible_conditions(settings)

    # One daily price timeline per company (the latest, most complete series).
    timelines: dict[str, tuple[list[str], list[float]]] = {}
    for company_id, history in db.execute(
        select(StockAnalysis.company_id, StockAnalysis.price_history)
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(StockAnalysis.id.in_(latest_ids()), *eligible)
    ):
        points = sorted(
            (str(p["date"]), float(p["close"]))
            for p in (history or [])
            if p.get("date") and p.get("close") is not None
        )
        if len(points) >= 22:
            timelines[company_id] = ([d for d, _ in points], [c for _, c in points])

    buckets: dict[str, dict[str, list[float]]] = {
        rating: {label: [] for _, label in HORIZONS} for rating in RATING_ORDER
    }
    benchmark: dict[str, list[float]] = {label: [] for _, label in HORIZONS}
    observations = 0
    earliest: str | None = None

    rows = db.execute(
        select(
            StockAnalysis.company_id,
            StockAnalysis.price_date,
            StockAnalysis.upside_pct,
            StockAnalysis.opportunity_score,
            StockAnalysis.risk_level,
            StockAnalysis.qualification,
            StockAnalysis.technical_indicators,
            Company.asset_type,
        )
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(*eligible)
        .order_by(StockAnalysis.as_of.asc())
    )

    for row in rows:
        timeline = timelines.get(row.company_id)
        if timeline is None:
            continue
        dates, closes = timeline
        entry_date = str(row.price_date)
        index = bisect_right(dates, entry_date) - 1
        if index < 0:
            continue
        entry = closes[index]
        if entry <= 0:
            continue

        indicators = row.technical_indicators or {}
        technical_only = row.qualification == "Technical Screen Only" or row.asset_type == "ETF"
        rating = derive_rating(
            upside_pct=_num(row.upside_pct),
            technical_only=technical_only,
            signal=indicators.get("signal"),
            rsi=_num(indicators.get("rsi14")),
            risk=row.risk_level,
            score=_num(row.opportunity_score),
            trend_cross=indicators.get("trend_cross"),
        )

        matured = False
        for days, label in HORIZONS:
            exit_index = index + days
            if exit_index < len(closes):
                forward = closes[exit_index] / entry - 1
                buckets[rating][label].append(forward)
                benchmark[label].append(forward)
                matured = True
        if matured:
            observations += 1
            if earliest is None or entry_date < earliest:
                earliest = entry_date
        if observations >= MAX_OBSERVATIONS:
            break

    return {
        "sample_size": observations,
        "since": earliest,
        "universe": len(timelines),
        "horizons": [{"days": days, "label": label} for days, label in HORIZONS],
        "benchmark": {label: _summarize(benchmark[label]) for _, label in HORIZONS},
        "ratings": [
            {
                "rating": rating,
                "by_horizon": {
                    label: _summarize(buckets[rating][label]) for _, label in HORIZONS
                },
            }
            for rating in RATING_ORDER
        ],
    }
