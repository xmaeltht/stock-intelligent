from decimal import Decimal


def build_etf_analysis(
    price: Decimal,
    volume: int | None,
    indicators: dict[str, object],
    history_points: int,
) -> dict[str, object]:
    """Build a technical/liquidity screen without inventing an ETF fair value."""
    confirmations = int(indicators.get("confirmations") or 0)
    rsi = indicators.get("rsi14")
    score = confirmations * 10
    if volume is not None:
        score += (
            30 if volume >= 5_000_000
            else 22 if volume >= 1_000_000
            else 14 if volume >= 100_000
            else 5
        )
    if isinstance(rsi, int | float) and 40 <= rsi <= 70:
        score += 10
    score = min(100, score)

    risks: list[dict[str, str]] = []
    if volume is None or volume < 100_000:
        risks.append({"severity": "High", "title": "Low or unavailable daily liquidity"})
    elif volume < 500_000:
        risks.append({"severity": "Moderate", "title": "Limited daily liquidity"})
    if isinstance(rsi, int | float) and rsi >= 75:
        risks.append({"severity": "Moderate", "title": "RSI indicates an extended price move"})

    confidence = "B" if history_points >= 200 and volume is not None else "C"
    risk_level = (
        "High"
        if any(item["severity"] == "High" for item in risks)
        else "Moderate"
        if risks
        else "Low"
    )
    signal = str(indicators.get("signal") or "Pending")
    return {
        "revenue_growth_pct": None,
        "fair_value": price,
        "bear_value": price,
        "bull_value": price,
        "upside_pct": 0.0,
        "opportunity_score": score,
        "confidence_grade": confidence,
        "risk_level": risk_level,
        "qualification": "ETF Technical Screen",
        "valuation_methods": [],
        "fundamentals": {},
        "catalysts": [{
            "category": "Technical",
            "title": f"{signal} trend",
            "detail": f"{confirmations} of 6 transparent trend checks currently pass.",
            "status": "Observed",
        }],
        "risks": risks,
        "thesis_breakers": [
            "Price loses both the 20-day and 50-day moving averages.",
            "Daily trading volume falls below the selected liquidity requirement.",
        ],
    }
