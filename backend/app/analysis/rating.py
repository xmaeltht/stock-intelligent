"""Deterministic action rating shared by the API and the backtest engine.

Mirrors the rules-based rating shown in the UI so historical snapshots can be
re-rated identically when measuring forward performance.
"""

RATING_ORDER = ("Strong Buy", "Buy", "Accumulate", "Hold", "Reduce", "Sell")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def derive_rating(
    *,
    upside_pct: float | None,
    technical_only: bool,
    signal: str | None,
    rsi: float | None,
    risk: str | None,
    score: float | None,
    trend_cross: str | None,
) -> str:
    points = 0.0
    normalized = (signal or "").lower()
    if normalized == "bullish":
        points += 2
    elif normalized == "bearish":
        points -= 2

    if not technical_only and upside_pct is not None:
        points += _clamp(upside_pct / 20.0, -3, 4)

    if trend_cross == "Golden cross":
        points += 1
    elif trend_cross == "Death cross":
        points -= 1

    if rsi is not None:
        if rsi >= 78:
            points -= 1
        elif rsi <= 30:
            points += 1
        elif 45 <= rsi <= 68:
            points += 0.5

    if risk == "Low":
        points += 0.5
    elif risk == "High":
        points -= 0.5

    if score is not None:
        points += _clamp((score - 50) / 25.0, -2, 2)

    if points >= 4:
        return "Strong Buy"
    if points >= 2:
        return "Buy"
    if points >= 0.75:
        return "Accumulate"
    if points > -0.75:
        return "Hold"
    if points > -2.25:
        return "Reduce"
    return "Sell"
