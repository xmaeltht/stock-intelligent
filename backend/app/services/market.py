"""Market-structure aggregations: average factor scores by sector.

Turns the per-security factor engine into a market map — how each sector scores
on Value / Quality / Momentum / Growth / Income right now — for the heatmap.
"""

from statistics import fmean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.services.queries import FACTOR_KEYS, eligible_conditions, latest_ids

MIN_SECTOR_COUNT = 5


def sector_factor_matrix(db: Session) -> dict:
    settings = get_settings()
    rows = db.execute(
        select(Company.sector, StockAnalysis.factor_scores)
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(StockAnalysis.id.in_(latest_ids()), *eligible_conditions(settings))
    ).all()

    buckets: dict[str, dict[str, list[float]]] = {}
    for sector, scores in rows:
        name = sector or "Unclassified"
        scores = scores or {}
        bucket = buckets.setdefault(name, {key: [] for key in FACTOR_KEYS})
        for key in FACTOR_KEYS:
            value = scores.get(key)
            if isinstance(value, int | float):
                bucket[key].append(float(value))

    sectors = []
    for name, bucket in buckets.items():
        count = max((len(bucket[key]) for key in FACTOR_KEYS), default=0)
        if count < MIN_SECTOR_COUNT:
            continue
        entry = {"sector": name, "count": count}
        for key in FACTOR_KEYS:
            entry[key] = round(fmean(bucket[key]), 1) if bucket[key] else None
        sectors.append(entry)

    sectors.sort(key=lambda item: item.get("composite") or 0, reverse=True)
    return {"factors": list(FACTOR_KEYS), "sectors": sectors}
