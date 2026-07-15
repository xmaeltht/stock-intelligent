"""Deterministic natural-language screener.

Turns a plain-English request ("profitable semiconductor names under $20 with a
golden cross and a rising dividend") into the structured filter parameters the
screener already understands. Rules-based keyword/pattern matching — no model, no
black box — so the interpretation is transparent and reproducible. Returns both
the filter kwargs and a human-readable list of what was understood.
"""

import re

SECTORS = {
    "technology": "Technology",
    "tech": "Technology",
    "semiconductor": "Technology",
    "software": "Technology",
    "health": "Health Care",
    "healthcare": "Health Care",
    "biotech": "Health Care",
    "pharma": "Health Care",
    "financial": "Financials",
    "bank": "Financials",
    "finance": "Financials",
    "energy": "Energy",
    "oil": "Energy",
    "industrial": "Industrials",
    "consumer discretionary": "Consumer Discretionary",
    "consumer staple": "Consumer Staples",
    "staples": "Consumer Staples",
    "material": "Materials",
    "utility": "Utilities",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "reit": "Real Estate",
    "communication": "Communication Services",
    "telecom": "Communication Services",
}

# (label, factor param, threshold) for quality-style phrases.
FACTOR_PHRASES = [
    (("high quality", "quality", "profitable", "durable"), "min_quality", 65),
    (("high growth", "fast growing", "growing", "growth"), "min_growth", 65),
    (("high momentum", "strong momentum", "momentum", "trending"), "min_momentum", 75),
    (("undervalued", "cheap", "value", "bargain"), "min_value", 65),
    (("high yield", "dividend", "income", "yield", "dividend payer", "paying"), "min_income", 45),
]

_NUM = r"\$?\s*([0-9][0-9,\.]*)\s*(k|m|b|million|billion|thousand)?"


def _to_number(raw: str, suffix: str | None) -> float:
    value = float(raw.replace(",", ""))
    factor = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
    if suffix:
        value *= factor.get(suffix.lower(), 1)
    return value


def parse_screen_query(query: str) -> tuple[dict, list[dict]]:
    text = f" {query.lower().strip()} "
    filters: dict = {"asset_type": "all"}
    interpretation: list[dict] = []

    def note(label: str) -> None:
        interpretation.append({"label": label})

    # Asset type
    if re.search(r"\betfs?\b|\bfunds?\b", text):
        filters["asset_type"] = "ETF"
        note("ETFs only")
    elif re.search(r"\bstocks?\b|\bcompan", text):
        filters["asset_type"] = "Stock"
        note("Stocks only")

    # Sector (longest phrase first)
    for keyword in sorted(SECTORS, key=len, reverse=True):
        if keyword in text:
            filters["sector"] = SECTORS[keyword]
            note(f"Sector: {SECTORS[keyword]}")
            break

    # Price bounds
    below = re.search(rf"(?:under|below|less than|cheaper than|<)\s*{_NUM}", text)
    if below:
        filters["max_price"] = _to_number(below.group(1), below.group(2))
        note(f"Price under ${filters['max_price']:,.0f}")
    above = re.search(rf"(?:over|above|more than|greater than|>)\s*{_NUM}", text)
    if above and "volume" not in text[max(0, above.start() - 12) : above.start()]:
        filters["min_price"] = _to_number(above.group(1), above.group(2))
        note(f"Price over ${filters['min_price']:,.0f}")

    # Volume / liquidity
    vol = re.search(rf"{_NUM}\s*(?:share)?\s*volume", text)
    if vol:
        filters["min_volume"] = int(_to_number(vol.group(1), vol.group(2)))
        note(f"Volume ≥ {filters['min_volume']:,}")
    elif re.search(r"\bliquid\b|high volume|heavily traded", text):
        filters["min_volume"] = 1_000_000
        note("Liquid (1M+ volume)")

    # Signals & technicals
    if "bullish" in text:
        filters["signal"] = "Bullish"
        note("Bullish signal")
    elif "bearish" in text:
        filters["signal"] = "Bearish"
        note("Bearish signal")
    if "golden cross" in text:
        filters["golden_cross"] = True
        note("Recent golden cross")
    if "oversold" in text:
        filters["max_rsi"] = 35
        note("Oversold (RSI ≤ 35)")
    if "overbought" in text:
        filters["min_rsi"] = 70
        note("Overbought (RSI ≥ 70)")

    # Upside / valuation
    upside = re.search(r"([0-9]{2,3})\s*%\s*(?:\+|or more)?\s*upside", text)
    if upside:
        filters["min_upside"] = float(upside.group(1))
        note(f"{upside.group(1)}%+ modeled upside")

    # Factor phrases
    for keywords, param, threshold in FACTOR_PHRASES:
        if any(keyword in text for keyword in keywords):
            filters[param] = max(filters.get(param, 0), threshold)
            note({
                "min_quality": "High quality",
                "min_growth": "High growth",
                "min_momentum": "High momentum",
                "min_value": "Undervalued (value factor)",
                "min_income": "Dividend / income",
            }[param])

    # Sort intent
    if re.search(r"\bbest\b|top\s|highest rated|strong buy", text):
        filters["sort_by"] = "rating"
        note("Ranked best-first")
    elif "momentum" in text:
        filters["sort_by"] = "factor_momentum"
    elif any(word in text for word in ("cheap", "undervalued", "value")):
        filters["sort_by"] = "factor_value"
    elif any(word in text for word in ("dividend", "yield", "income")):
        filters["sort_by"] = "factor_income"

    if not interpretation:
        # Nothing recognized — fall back to a free-text search.
        filters["search"] = query.strip()[:100]
        note("Free-text search")

    return filters, interpretation
