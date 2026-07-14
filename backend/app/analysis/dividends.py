"""Build a rich dividend profile from real per-payment dividend events.

Per-payment cash dividends come from the price provider (Yahoo) at no extra
request. Multi-year annual dividend-per-share history from SEC filings (when
available) sharpens the growth streak. Everything is deterministic.
"""

from datetime import date

FREQUENCY_LABELS = {12: "Monthly", 4: "Quarterly", 2: "Semi-Annual", 1: "Annual"}


def _to_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _infer_frequency(dates: list[date]) -> tuple[str | None, int | None]:
    """Payments per year, inferred from how many landed in the trailing year."""
    if not dates:
        return None, None
    anchor = dates[-1]
    recent = [d for d in dates if (anchor - d).days <= 370]
    count = len(recent)
    if count >= 11:
        return "Monthly", 12
    if count >= 3:
        return "Quarterly", 4
    if count == 2:
        return "Semi-Annual", 2
    if count == 1:
        return "Annual", 1
    return "Irregular", None


def _sum_between(
    events: list[tuple[date, float]], newest: date, lo_days: int, hi_days: int
) -> float:
    return sum(
        amount
        for when, amount in events
        if lo_days < (newest - when).days <= hi_days
    )


def _annual_from_events(events: list[tuple[date, float]]) -> list[dict[str, object]]:
    by_year: dict[int, float] = {}
    for when, amount in events:
        by_year[when.year] = by_year.get(when.year, 0.0) + amount
    return [
        {"year": str(year), "value": round(total, 4)}
        for year, total in sorted(by_year.items())
    ]


def _growth_streak(annual: list[dict[str, object]]) -> int:
    """Consecutive most-recent complete years with a rising dividend."""
    values = [float(item["value"]) for item in annual]
    if len(values) < 2:
        return 0
    streak = 0
    for index in range(len(values) - 1, 0, -1):
        if values[index] > values[index - 1] > 0:
            streak += 1
        else:
            break
    return streak


def build_dividend_profile(
    events: list[dict[str, object]],
    price: float,
    eps: float | None = None,
    market_cap: float | None = None,
    buyback_net: float | None = None,
    sec_annual_dps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    parsed = sorted(
        (
            (_to_date(item.get("date")), float(item.get("amount") or 0.0))
            for item in (events or [])
        ),
        key=lambda pair: pair[0] or date.min,
    )
    parsed = [(when, amount) for when, amount in parsed if when and amount > 0]

    # Fall back to SEC annual DPS if the provider returned no per-payment events.
    sec_annual = [
        {"year": str(item["fy_end"])[:4], "value": round(float(item["value"]), 4)}
        for item in (sec_annual_dps or [])
        if float(item.get("value") or 0) > 0
    ]

    if not parsed and not sec_annual:
        return {"pays": False}

    buyback_yield_pct = (
        round(buyback_net / market_cap * 100, 2)
        if buyback_net is not None and market_cap and market_cap > 0
        else None
    )

    if not parsed:
        # SEC-only path: no payment schedule, just the latest annual figure.
        latest_annual = float(sec_annual[-1]["value"])
        yield_pct = round(latest_annual / price * 100, 2) if price > 0 else None
        return {
            "pays": True,
            "source": "SEC annual filings",
            "annual_amount_ttm": round(latest_annual, 4),
            "forward_annual": round(latest_annual, 4),
            "yield_pct": yield_pct,
            "forward_yield_pct": yield_pct,
            "frequency": None,
            "payments_per_year": None,
            "last_ex_date": None,
            "last_amount": None,
            "growth_1y_pct": None,
            "growth_streak_years": _growth_streak(sec_annual),
            "payout_ratio_pct": (
                round(latest_annual / eps * 100, 1) if eps and eps > 0 else None
            ),
            "buyback_yield_pct": buyback_yield_pct,
            "shareholder_yield_pct": (
                round((yield_pct or 0) + (buyback_yield_pct or 0), 2)
                if yield_pct is not None or buyback_yield_pct is not None
                else None
            ),
            "payments": [],
            "annual": sec_annual,
        }

    dates = [when for when, _ in parsed]
    frequency, per_year = _infer_frequency(dates)
    anchor = dates[-1]
    last_amount = parsed[-1][1]
    ttm = _sum_between(parsed, anchor, -1, 365)
    prior_ttm = _sum_between(parsed, anchor, 365, 730)
    forward_annual = last_amount * per_year if per_year else ttm
    yield_pct = round(ttm / price * 100, 2) if price > 0 else None
    forward_yield_pct = round(forward_annual / price * 100, 2) if price > 0 else None
    growth_1y = (
        round((ttm / prior_ttm - 1) * 100, 1) if prior_ttm > 0 else None
    )
    # Prefer the longer SEC annual series for the streak/chart when we have it.
    annual = sec_annual if len(sec_annual) >= 3 else _annual_from_events(parsed)

    payments = [
        {"date": when.isoformat(), "amount": round(amount, 4)}
        for when, amount in reversed(parsed)
    ][:40]

    return {
        "pays": True,
        "source": "Per-payment dividend events",
        "annual_amount_ttm": round(ttm, 4),
        "forward_annual": round(forward_annual, 4),
        "yield_pct": yield_pct,
        "forward_yield_pct": forward_yield_pct,
        "frequency": frequency,
        "payments_per_year": per_year,
        "last_ex_date": anchor.isoformat(),
        "last_amount": round(last_amount, 4),
        "growth_1y_pct": growth_1y,
        "growth_streak_years": _growth_streak(annual),
        "payout_ratio_pct": round(ttm / eps * 100, 1) if eps and eps > 0 else None,
        "buyback_yield_pct": buyback_yield_pct,
        "shareholder_yield_pct": (
            round((yield_pct or 0) + (buyback_yield_pct or 0), 2)
            if yield_pct is not None or buyback_yield_pct is not None
            else None
        ),
        "payments": payments,
        "annual": annual,
    }
