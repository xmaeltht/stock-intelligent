from decimal import Decimal

from app.analysis.etf import build_etf_analysis


def test_etf_screen_does_not_invent_upside() -> None:
    result = build_etf_analysis(
        Decimal("20"),
        2_000_000,
        {"confirmations": 3, "rsi14": 55, "signal": "Bullish"},
        252,
    )

    assert result["fair_value"] == Decimal("20")
    assert result["upside_pct"] == 0.0
    assert result["valuation_methods"] == []
    assert result["fundamentals"] == {}
    assert result["qualification"] == "ETF Technical Screen"
    # 3 of 6 confirmations (30) + 1M+ volume (22) + RSI in band (10)
    assert result["opportunity_score"] == 62
