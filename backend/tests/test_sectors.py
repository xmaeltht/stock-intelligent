from app.analysis.sectors import classify_sector, sector_for_etf, sector_for_sic


def test_sic_ranges_and_overrides() -> None:
    assert sector_for_sic(7372) == "Technology"  # prepackaged software (override)
    assert sector_for_sic(3674) == "Technology"  # semiconductors (override)
    assert sector_for_sic(2834) == "Health Care"  # pharmaceutical preparations
    assert sector_for_sic(6021) == "Financials"  # national commercial banks
    assert sector_for_sic(1311) == "Energy"  # crude petroleum & natural gas
    assert sector_for_sic(4911) == "Utilities"  # electric services
    assert sector_for_sic(6798) == "Real Estate"  # REIT
    assert sector_for_sic(5411) == "Consumer Staples"  # grocery stores


def test_sic_unknown_is_other() -> None:
    assert sector_for_sic(None) == "Other"
    assert sector_for_sic("n/a") == "Other"
    assert sector_for_sic(9999) == "Other"


def test_etf_name_classification() -> None:
    assert sector_for_etf("Technology Select Sector SPDR Fund") == "Technology"
    assert sector_for_etf("iShares Biotechnology ETF") == "Health Care"
    assert sector_for_etf("Energy Select Sector SPDR") == "Energy"
    assert sector_for_etf("iShares 20+ Year Treasury Bond ETF") == "Fixed Income"
    assert sector_for_etf("Vanguard Total Stock Market ETF") == "Diversified / Fund"


def test_classify_dispatch() -> None:
    assert classify_sector("ETF", name="Financial Select Sector SPDR") == "Financials"
    assert classify_sector("Stock", sic=2834) == "Health Care"
