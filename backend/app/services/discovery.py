"""Live discovery radar: scan the latest analysis of every security and surface
what's *notable right now* across the whole market.

This is the payoff of analyzing the entire universe continuously — a single-stock
site cannot tell you which of 12,000 names just crossed, broke out, spiked on
volume, or flipped into a value setup. Everything is derived from the freshest
stored snapshot (kept current by the live price loop), so the feed feels live.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.analysis.valuation import IMPLAUSIBLE_UPSIDE_PCT
from app.core.config import get_settings
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis

PER_CATEGORY = 60

CATEGORIES = [
    {"key": "golden_cross", "label": "Golden crosses",
     "description": "50-day crossed above the 200-day within the last week."},
    {"key": "breakout", "label": "52-week breakouts",
     "description": "Trading at or near a fresh 52-week high."},
    {"key": "unusual_volume", "label": "Unusual volume",
     "description": "Volume running well above the 50-day average."},
    {"key": "gainers", "label": "Big gainers",
     "description": "Largest 1-day advances."},
    {"key": "value", "label": "New value setups",
     "description": "Modeled fair value implies 90%+ upside."},
    {"key": "momentum", "label": "Momentum leaders",
     "description": "Top-decile momentum factor scores."},
    {"key": "oversold", "label": "Oversold",
     "description": "RSI in deeply oversold territory."},
    {"key": "overbought", "label": "Overbought",
     "description": "RSI in extended overbought territory."},
    {"key": "decliners", "label": "Big decliners",
     "description": "Largest 1-day declines."},
    {"key": "breakdown", "label": "52-week breakdowns",
     "description": "Trading at or near a fresh 52-week low."},
    {"key": "death_cross", "label": "Death crosses",
     "description": "50-day crossed below the 200-day within the last week."},
]


def _latest_ids():
    prior = aliased(StockAnalysis)
    latest_time = (
        select(func.max(prior.as_of))
        .where(prior.company_id == StockAnalysis.company_id)
        .correlate(StockAnalysis)
        .scalar_subquery()
    )
    return select(StockAnalysis.id).where(StockAnalysis.as_of == latest_time)


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _event(base: dict, headline: str, significance: float) -> dict:
    return {**base, "headline": headline, "significance": round(significance, 2)}


def build_radar(db: Session) -> dict:
    settings = get_settings()
    rows = db.execute(
        select(
            Company.ticker,
            Company.name,
            Company.sector,
            Company.asset_type,
            StockAnalysis.current_price,
            StockAnalysis.price_as_of,
            StockAnalysis.upside_pct,
            StockAnalysis.qualification,
            StockAnalysis.volume,
            StockAnalysis.technical_indicators,
            StockAnalysis.factor_scores,
        )
        .join(Company, Company.id == StockAnalysis.company_id)
        .where(StockAnalysis.id.in_(_latest_ids()), *_eligible(settings))
    ).all()

    events: dict[str, list[dict]] = {cat["key"]: [] for cat in CATEGORIES}
    newest: str | None = None

    for row in rows:
        indicators = row.technical_indicators or {}
        factors = row.factor_scores or {}
        change_1d = _num(indicators.get("change_1d_pct"))
        rsi = _num(indicators.get("rsi14"))
        volume = row.volume
        vol_avg = _num(indicators.get("volume_avg50"))
        range_pos = _num(indicators.get("range_position_pct"))
        cross = indicators.get("trend_cross")
        age = _num(indicators.get("trend_cross_age_days"))
        price = float(row.current_price)
        as_of = row.price_as_of.isoformat() if row.price_as_of else None
        if as_of and (newest is None or as_of > newest):
            newest = as_of

        base = {
            "ticker": row.ticker,
            "name": row.name,
            "sector": row.sector or "Unclassified",
            "asset_type": row.asset_type,
            "price": price,
            "change_1d_pct": change_1d,
            "as_of": as_of,
        }

        if cross == "Golden cross" and age is not None and age <= 5:
            events["golden_cross"].append(_event(base, f"Golden cross {int(age)}d ago", 10 - age))
        if cross == "Death cross" and age is not None and age <= 5:
            events["death_cross"].append(_event(base, f"Death cross {int(age)}d ago", 10 - age))
        if range_pos is not None and range_pos >= 98:
            events["breakout"].append(
                _event(base, f"At {range_pos:.0f}% of 52-week range", range_pos + (change_1d or 0))
            )
        if range_pos is not None and range_pos <= 2:
            events["breakdown"].append(
                _event(base, f"At {range_pos:.0f}% of 52-week range", 100 - range_pos)
            )
        if volume and vol_avg and vol_avg > 0 and volume / vol_avg >= 2.5:
            ratio = volume / vol_avg
            events["unusual_volume"].append(_event(base, f"{ratio:.1f}x average volume", ratio))
        if change_1d is not None and change_1d >= 5:
            events["gainers"].append(_event(base, f"+{change_1d:.1f}% today", change_1d))
        if change_1d is not None and change_1d <= -5:
            events["decliners"].append(_event(base, f"{change_1d:.1f}% today", -change_1d))
        if rsi is not None and rsi <= 22:
            events["oversold"].append(_event(base, f"RSI {rsi:.0f}", 30 - rsi))
        if rsi is not None and rsi >= 80:
            events["overbought"].append(_event(base, f"RSI {rsi:.0f}", rsi))
        if (
            row.asset_type == "Stock"
            and row.qualification != "Technical Screen Only"
            and row.upside_pct is not None
            and 90 <= row.upside_pct <= IMPLAUSIBLE_UPSIDE_PCT
        ):
            events["value"].append(
                _event(base, f"{row.upside_pct:.0f}% modeled upside", row.upside_pct)
            )
        momentum = _num(factors.get("momentum"))
        if momentum is not None and momentum >= 85:
            events["momentum"].append(_event(base, f"Momentum factor {momentum:.0f}", momentum))

    categories = []
    for cat in CATEGORIES:
        items = sorted(events[cat["key"]], key=lambda item: item["significance"], reverse=True)
        categories.append({**cat, "count": len(items), "items": items[:PER_CATEGORY]})

    return {
        "generated_at": newest,
        "universe": len(rows),
        "total_events": sum(len(events[cat["key"]]) for cat in CATEGORIES),
        "categories": categories,
    }


def _eligible(settings):
    return (
        Company.is_active.is_(True),
        Company.is_research_eligible.is_(True),
        or_(Company.cik.is_not(None), Company.asset_type == "ETF"),
        Company.exchange.in_(settings.exchange_list),
    )
