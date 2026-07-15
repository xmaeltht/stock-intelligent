from app.services.screen_parser import parse_screen_query


def test_parses_sector_price_and_technical() -> None:
    filters, interp = parse_screen_query(
        "profitable semiconductor stocks under $20 with a golden cross"
    )
    assert filters["sector"] == "Technology"
    assert filters["asset_type"] == "Stock"
    assert filters["max_price"] == 20
    assert filters["golden_cross"] is True
    assert filters["min_quality"] >= 65  # "profitable"
    assert any("golden cross" in item["label"].lower() for item in interp)


def test_parses_etf_and_income() -> None:
    filters, _ = parse_screen_query("high yield dividend ETFs")
    assert filters["asset_type"] == "ETF"
    assert filters["min_income"] >= 45
    assert filters["sort_by"] == "factor_income"


def test_parses_upside_and_oversold() -> None:
    filters, _ = parse_screen_query("undervalued names with 90% upside that are oversold")
    assert filters["min_upside"] == 90
    assert filters["max_rsi"] == 35
    assert filters["min_value"] >= 65


def test_volume_and_momentum() -> None:
    filters, _ = parse_screen_query("liquid high momentum stocks")
    assert filters["min_volume"] == 1_000_000
    assert filters["min_momentum"] >= 75
    assert filters["sort_by"] == "factor_momentum"


def test_unrecognized_falls_back_to_search() -> None:
    filters, interp = parse_screen_query("Berkshire Hathaway")
    assert filters.get("search")
    assert interp[-1]["label"] == "Free-text search"
