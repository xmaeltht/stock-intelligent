"""Fast intraday price-refresh loop.

Runs alongside the heavy fundamental analyzer. It cheaply refreshes the current
price / 1-day move / volume for already-analyzed securities far more often than
the deep loop can re-run a full valuation, so the screener feels live. It never
recomputes fundamentals — only the market-facing fields — and is fully
best-effort: a failed provider call just leaves prior values in place.
"""

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload

from app.core.config import Settings
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.providers.nasdaq import LiveQuote, NasdaqProvider

EASTERN = ZoneInfo("America/New_York")


def market_session(now: datetime | None = None) -> str:
    """Current US trading session in ET:
    'pre' (4:00-9:30), 'regular' (9:30-16:00), 'after' (16:00-20:00),
    'overnight' (20:00-4:00 on a weekday/into a weekday), or 'closed' (weekend).
    Holidays are treated as normal days (prices simply don't move)."""
    moment = (now or datetime.now(UTC)).astimezone(EASTERN)
    minutes = moment.hour * 60 + moment.minute
    weekday = moment.weekday()  # Mon=0 .. Sun=6
    if weekday < 5:
        if 4 * 60 <= minutes < 9 * 60 + 30:
            return "pre"
        if 9 * 60 + 30 <= minutes < 16 * 60:
            return "regular"
        if 16 * 60 <= minutes < 20 * 60:
            return "after"
    # Overnight window: weeknights, plus Sunday evening ahead of Monday's pre-market.
    if (weekday < 5 and minutes >= 20 * 60) or (weekday < 5 and minutes < 4 * 60) or (
        weekday == 6 and minutes >= 20 * 60
    ):
        return "overnight"
    return "closed"


# Sessions during which the fast loop runs at full cadence.
ACTIVE_SESSIONS = {"pre", "regular", "after"}


def is_market_open(now: datetime | None = None) -> bool:
    """True only during the regular session (kept for the summary badge)."""
    return market_session(now) == "regular"


def _latest_ids_subquery():
    prior = aliased(StockAnalysis)
    latest_time = (
        select(func.max(prior.as_of))
        .where(prior.company_id == StockAnalysis.company_id)
        .correlate(StockAnalysis)
        .scalar_subquery()
    )
    return select(StockAnalysis.id).where(StockAnalysis.as_of == latest_time)


def select_live_targets(
    session: Session, settings: Settings, limit: int
) -> list[StockAnalysis]:
    """The latest analysis rows whose price is most stale, refreshed first."""
    statement = (
        select(StockAnalysis)
        .join(Company, Company.id == StockAnalysis.company_id)
        .options(joinedload(StockAnalysis.company))
        .where(
            StockAnalysis.id.in_(_latest_ids_subquery()),
            Company.is_active.is_(True),
            Company.is_research_eligible.is_(True),
            or_(Company.cik.is_not(None), Company.asset_type == "ETF"),
            Company.exchange.in_(settings.exchange_list),
        )
        .order_by(
            StockAnalysis.price_as_of.asc().nullsfirst(),
            StockAnalysis.as_of.asc(),
        )
        .limit(limit)
    )
    return list(session.scalars(statement))


def _prior_close(history: list[dict], today_iso: str) -> float | None:
    if not history:
        return None
    last = history[-1]
    try:
        if str(last.get("date")) == today_iso and len(history) >= 2:
            return float(history[-2]["close"])
        return float(last["close"])
    except (KeyError, TypeError, ValueError):
        return None


def apply_live_quote(analysis: StockAnalysis, quote: LiveQuote, now: datetime) -> bool:
    """Update the market-facing fields of one analysis row in place. Returns True
    if anything meaningful changed."""
    try:
        price = Decimal(str(quote.price))
    except (InvalidOperation, ValueError):
        return False
    if price <= 0:
        return False

    today_iso = now.astimezone(EASTERN).date().isoformat()
    history = list(analysis.price_history or [])
    prior = _prior_close(history, today_iso)

    change_pct = quote.change_pct
    if change_pct is None and prior:
        change_pct = float((price / Decimal(str(prior)) - 1) * 100)

    price_float = float(price)
    if history and str(history[-1].get("date")) == today_iso:
        bar = dict(history[-1])
        bar["close"] = price_float
        bar["high"] = max(float(bar.get("high") or price_float), price_float)
        bar["low"] = min(float(bar.get("low") or price_float), price_float)
        if quote.volume is not None:
            bar["volume"] = quote.volume
        history[-1] = bar
    else:
        history.append(
            {
                "date": today_iso,
                "open": price_float,
                "high": price_float,
                "low": price_float,
                "close": price_float,
                "volume": quote.volume,
            }
        )
    analysis.price_history = history
    analysis.current_price = price
    analysis.price_date = date.fromisoformat(today_iso)
    if quote.volume is not None:
        analysis.volume = quote.volume

    if analysis.fair_value and price > 0:
        analysis.upside_pct = float((Decimal(str(analysis.fair_value)) / price - 1) * 100)

    indicators = dict(analysis.technical_indicators or {})
    if change_pct is not None:
        indicators["change_1d_pct"] = round(change_pct, 2)
    # Keep the sparkline live: replace today's trailing point (or append it).
    spark = list(indicators.get("spark") or [])
    if spark:
        if str(history[-1].get("date")) == today_iso and len(history) >= 2:
            spark[-1] = round(price_float, 4)
        else:
            spark.append(round(price_float, 4))
        indicators["spark"] = spark[-32:]
    analysis.technical_indicators = indicators

    analysis.price_as_of = now
    return True


def run_live_cycle(
    session: Session, settings: Settings, prices: NasdaqProvider, now: datetime | None = None
) -> int:
    """Refresh one batch of the stalest prices. Returns how many were updated."""
    moment = now or datetime.now(UTC)
    targets = select_live_targets(session, settings, settings.live_quote_batch_size)
    if not targets:
        return 0
    by_ticker = {row.company.ticker.upper(): row for row in targets if row.company}
    quotes = prices.batch_quotes(list(by_ticker), settings.live_quote_chunk_size)
    updated = 0
    for ticker, quote in quotes.items():
        analysis = by_ticker.get(ticker.upper())
        if analysis is not None and apply_live_quote(analysis, quote, moment):
            updated += 1
    if updated:
        session.commit()
    return updated
