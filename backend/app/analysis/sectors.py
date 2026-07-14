"""Map SEC SIC codes (and ETF names) to coarse GICS-style sectors.

SIC is the classification the SEC actually publishes per filer. The mapping to
GICS-style sectors is deterministic and intentionally coarse — it is meant for
browsing/grouping, not precise index construction.
"""

# Specific 4-digit SIC codes whose range default would be wrong.
SIC_OVERRIDES: dict[int, str] = {
    2833: "Health Care", 2834: "Health Care", 2835: "Health Care", 2836: "Health Care",
    3826: "Health Care", 3841: "Health Care", 3842: "Health Care", 3843: "Health Care",
    3845: "Health Care", 8000: "Health Care", 8011: "Health Care", 8060: "Health Care",
    8071: "Health Care", 8090: "Health Care", 8093: "Health Care",
    3571: "Technology", 3572: "Technology", 3576: "Technology", 3577: "Technology",
    3661: "Technology", 3663: "Technology", 3669: "Technology", 3670: "Technology",
    3674: "Technology", 3677: "Technology", 3678: "Technology", 3679: "Technology",
    7370: "Technology", 7371: "Technology", 7372: "Technology", 7373: "Technology",
    7374: "Technology", 7377: "Technology", 7379: "Technology",
    3711: "Consumer Discretionary", 3714: "Consumer Discretionary", 3716: "Consumer Discretionary",
    5400: "Consumer Staples", 5411: "Consumer Staples", 2080: "Consumer Staples",
    2082: "Consumer Staples", 2086: "Consumer Staples",
    4812: "Communication Services", 4813: "Communication Services", 4899: "Communication Services",
    7812: "Communication Services", 7900: "Communication Services", 2711: "Communication Services",
    1311: "Energy", 2911: "Energy", 1381: "Energy", 1389: "Energy",
    6798: "Real Estate", 6500: "Real Estate", 6512: "Real Estate",
}

# (low, high, sector) — first matching range wins.
SIC_RANGES: list[tuple[int, int, str]] = [
    (100, 999, "Consumer Staples"),
    (1000, 1099, "Materials"),
    (1200, 1299, "Energy"),
    (1300, 1399, "Energy"),
    (1400, 1499, "Materials"),
    (1500, 1799, "Industrials"),
    (2000, 2199, "Consumer Staples"),
    (2200, 2399, "Consumer Discretionary"),
    (2400, 2599, "Industrials"),
    (2600, 2699, "Materials"),
    (2700, 2799, "Communication Services"),
    (2800, 2899, "Materials"),
    (2900, 2999, "Energy"),
    (3000, 3199, "Consumer Discretionary"),
    (3200, 3399, "Materials"),
    (3400, 3599, "Industrials"),
    (3600, 3699, "Technology"),
    (3700, 3799, "Industrials"),
    (3800, 3899, "Health Care"),
    (3900, 3999, "Consumer Discretionary"),
    (4000, 4799, "Industrials"),
    (4800, 4899, "Communication Services"),
    (4900, 4999, "Utilities"),
    (5000, 5199, "Industrials"),
    (5200, 5999, "Consumer Discretionary"),
    (6000, 6299, "Financials"),
    (6300, 6499, "Financials"),
    (6500, 6599, "Real Estate"),
    (6700, 6799, "Financials"),
    (7000, 7299, "Consumer Discretionary"),
    (7300, 7399, "Technology"),
    (7400, 7999, "Consumer Discretionary"),
    (8000, 8099, "Health Care"),
    (8100, 8999, "Industrials"),
]

# ETF name keyword → sector (checked in order; Health Care before Technology so
# "biotechnology" is not captured by the "technolog" keyword).
ETF_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("biotech", "health", "pharma", "medical", "genomic"), "Health Care"),
    (
        ("semiconductor", "technolog", "software", "internet", "fintech", "cyber", "cloud", "ai "),
        "Technology",
    ),
    (("bank", "financ", "insurance"), "Financials"),
    (("energy", "oil", "gas", "solar", "clean energy", "uranium"), "Energy"),
    (("real estate", "reit", "mortgage"), "Real Estate"),
    (("utilit", "infrastructure"), "Utilities"),
    (("consumer", "retail", "discretionary"), "Consumer Discretionary"),
    (("staple", "food", "beverage"), "Consumer Staples"),
    (("industrial", "aerospace", "defense", "transport"), "Industrials"),
    (("material", "metal", "mining", "gold", "silver", "copper", "commodit"), "Materials"),
    (("communication", "telecom", "media", "social"), "Communication Services"),
    (
        ("bond", "treasury", "aggregate", "income", "municipal", "yield", "fixed income", "credit"),
        "Fixed Income",
    ),
]


def sector_for_sic(sic: object) -> str:
    try:
        code = int(str(sic).strip())
    except (TypeError, ValueError):
        return "Other"
    if code in SIC_OVERRIDES:
        return SIC_OVERRIDES[code]
    for low, high, sector in SIC_RANGES:
        if low <= code <= high:
            return sector
    return "Other"


def sector_for_etf(name: str) -> str:
    lowered = (name or "").lower()
    for keywords, sector in ETF_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return sector
    return "Diversified / Fund"


def classify_sector(asset_type: str, sic: object = None, name: str = "") -> str:
    if asset_type == "ETF":
        return sector_for_etf(name)
    return sector_for_sic(sic)
