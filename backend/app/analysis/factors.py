"""Deterministic multi-factor scoring engine.

Every security is scored 0-100 on five independent factors — Value, Quality,
Momentum, Growth, and Income (yield) — plus a composite. Scores are a transparent,
monotonic function of metrics the analyzer already computes, so they are fully
reproducible and auditable (no black box, no ML). Universe/sector percentile
ranking is applied separately at query time.
"""


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _score(base: float, *contributions: float) -> float:
    return round(_clamp(base + sum(contributions), 0.0, 100.0), 1)


def value_score(upside_pct: float | None, ratios: dict) -> float:
    """Cheap relative to fundamentals scores high."""
    pe = _num(ratios.get("price_to_earnings"))
    ps = _num(ratios.get("price_to_sales"))
    pfcf = _num(ratios.get("price_to_fcf"))
    pb = _num(ratios.get("price_to_book"))
    contributions = [
        _clamp((upside_pct or 0.0) / 2.5, -25, 40),
        0.0 if pe is None else 15 if pe < 10 else 8 if pe < 18 else 0 if pe < 30 else -10,
        0.0 if ps is None else 10 if ps < 1 else 5 if ps < 3 else 0 if ps < 8 else -8,
        0.0 if pfcf is None else 12 if pfcf < 15 else 4 if pfcf < 25 else 0 if pfcf < 40 else -8,
        0.0 if pb is None else 6 if pb < 1.5 else 2 if pb < 4 else -4,
    ]
    return _score(45.0, *contributions)


def quality_score(
    margins: dict,
    net_income: float | None,
    free_cash_flow: float | None,
    cash: float | None,
    debt: float | None,
    equity: float | None,
) -> float:
    net_margin = _num(margins.get("net_pct"))
    op_margin = _num(margins.get("operating_pct"))
    fcf_margin = _num(margins.get("fcf_pct"))
    roe = (net_income / equity * 100) if net_income is not None and equity and equity > 0 else None
    contributions = [
        _clamp((net_margin or 0.0) * 0.8, -20, 25),
        _clamp((op_margin or 0.0) * 0.5, -12, 15),
        _clamp((fcf_margin or 0.0) * 0.8, -12, 18),
        8 if (net_income or 0) > 0 else -12,
        6 if (free_cash_flow or 0) > 0 else -8,
        6 if (cash or 0) >= (debt or 0) else -4,
        _clamp((roe or 0.0) * 0.4, -10, 15),
    ]
    return _score(45.0, *contributions)


def momentum_score(indicators: dict, price: float) -> float:
    change_5d = _num(indicators.get("change_5d_pct")) or 0.0
    change_20d = _num(indicators.get("change_20d_pct")) or 0.0
    sma50 = _num(indicators.get("sma50"))
    sma200 = _num(indicators.get("sma200"))
    rsi = _num(indicators.get("rsi14"))
    cross = indicators.get("trend_cross")
    dist50 = ((price / sma50 - 1) * 100) if sma50 and sma50 > 0 else 0.0
    dist200 = ((price / sma200 - 1) * 100) if sma200 and sma200 > 0 else 0.0
    rsi_bonus = 0.0
    if rsi is not None:
        rsi_bonus = 6 if 55 <= rsi <= 70 else -6 if rsi >= 78 else -4 if rsi <= 30 else 2
    contributions = [
        _clamp(change_20d * 1.0, -20, 25),
        _clamp(change_5d * 1.5, -12, 15),
        _clamp(dist50 * 0.8, -12, 15),
        _clamp(dist200 * 0.5, -12, 18),
        8 if cross == "Golden cross" else -8 if cross == "Death cross" else 0,
        rsi_bonus,
    ]
    return _score(50.0, *contributions)


def growth_score(
    revenue_growth_pct: float | None,
    revenue_cagr_pct: float | None,
    net_income_history: list,
    free_cash_flow: float | None,
) -> float:
    ni_growth = 0.0
    values = [float(item["value"]) for item in (net_income_history or []) if "value" in item]
    if len(values) >= 2 and values[-2] > 0:
        ni_growth = (values[-1] / values[-2] - 1) * 100
    contributions = [
        _clamp((revenue_growth_pct or 0.0) * 1.0, -20, 30),
        _clamp((revenue_cagr_pct or 0.0) * 1.2, -10, 20),
        _clamp(ni_growth * 0.4, -12, 18),
        6 if (free_cash_flow or 0) > 0 else -4,
    ]
    return _score(45.0, *contributions)


def income_score(dividend: dict) -> float:
    if not dividend or not dividend.get("pays"):
        # Net buybacks still return capital even without a dividend.
        buyback = _num(dividend.get("buyback_yield_pct")) if dividend else None
        return _score(25.0, _clamp((buyback or 0.0) * 2.5, -8, 20))
    dividend_yield = _num(dividend.get("yield_pct")) or 0.0
    shareholder = _num(dividend.get("shareholder_yield_pct")) or dividend_yield
    streak = _num(dividend.get("growth_streak_years")) or 0.0
    payout = _num(dividend.get("payout_ratio_pct"))
    payout_bonus = 0.0
    if payout is not None:
        payout_bonus = 6 if payout < 60 else -6 if payout > 90 else 0
    contributions = [
        _clamp(dividend_yield * 6.0, 0, 45),
        _clamp((shareholder - dividend_yield) * 3.0, -8, 20),
        _clamp(streak * 3.0, 0, 15),
        payout_bonus,
    ]
    return _score(35.0, *contributions)


def build_factor_scores(
    *,
    upside_pct: float | None,
    indicators: dict,
    fundamentals: dict,
    dividend: dict,
    net_income: float | None,
    free_cash_flow: float | None,
    cash: float | None,
    debt: float | None,
    equity: float | None,
    revenue_growth_pct: float | None,
    price: float,
) -> dict[str, float]:
    ratios = fundamentals.get("ratios") or {}
    margins = fundamentals.get("margins") or {}
    value = value_score(upside_pct, ratios)
    quality = quality_score(margins, net_income, free_cash_flow, cash, debt, equity)
    momentum = momentum_score(indicators, price)
    growth = growth_score(
        revenue_growth_pct,
        _num(fundamentals.get("revenue_cagr_pct")),
        fundamentals.get("net_income_history") or [],
        free_cash_flow,
    )
    income = income_score(dividend or {})
    # Composite leans on quality and value (durable), with momentum/growth/income
    # as tilts — a balanced blend rather than chasing any single factor.
    composite = round(
        value * 0.26 + quality * 0.28 + momentum * 0.18 + growth * 0.18 + income * 0.10, 1
    )
    return {
        "value": value,
        "quality": quality,
        "momentum": momentum,
        "growth": growth,
        "income": income,
        "composite": composite,
    }
