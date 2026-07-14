from decimal import Decimal

import pytest

from app.analysis.valuation import EMPTY_FINANCIALS, build_analysis


def _financials(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = dict(EMPTY_FINANCIALS)
    base.update(overrides)
    return base


def test_profitable_company_uses_all_five_methods() -> None:
    financials = _financials(
        revenue=Decimal("1000000000"),
        previous_revenue=Decimal("800000000"),
        net_income=Decimal("150000000"),
        free_cash_flow=Decimal("120000000"),
        cash=Decimal("300000000"),
        debt=Decimal("100000000"),
        shares_outstanding=Decimal("100000000"),
        eps=Decimal("1.50"),
        equity=Decimal("900000000"),
        operating_income=Decimal("180000000"),
        gross_profit=Decimal("550000000"),
        revenue_history=[
            {"fy_end": "2022-12-31", "value": 600000000.0},
            {"fy_end": "2023-12-31", "value": 700000000.0},
            {"fy_end": "2024-12-31", "value": 800000000.0},
            {"fy_end": "2025-12-31", "value": 1000000000.0},
        ],
    )

    result = build_analysis(financials, Decimal("10"))

    models = {method["model"] for method in result["valuation_methods"]}
    assert models == {
        "Revenue multiple",
        "Free cash flow multiple",
        "Operating income multiple",
        "Book value multiple",
        "Earnings multiple",
    }
    assert result["confidence_grade"] == "A"
    assert result["fundamentals"]["margins"]["net_pct"] == 15.0
    assert result["fundamentals"]["ratios"]["price_to_earnings"] == 6.67
    assert result["fundamentals"]["revenue_cagr_pct"] == pytest.approx(18.6, abs=0.2)
    assert result["upside_pct"] > 0


def test_dividend_metrics_are_computed() -> None:
    financials = _financials(
        revenue=Decimal("1000000000"),
        previous_revenue=Decimal("900000000"),
        net_income=Decimal("150000000"),
        free_cash_flow=Decimal("120000000"),
        cash=Decimal("300000000"),
        debt=Decimal("100000000"),
        shares_outstanding=Decimal("100000000"),
        eps=Decimal("2.00"),
        equity=Decimal("900000000"),
        dividend_per_share=Decimal("1.00"),
        previous_dividend_per_share=Decimal("0.80"),
        dividend_history=[
            {"fy_end": "2022-12-31", "value": 0.70},
            {"fy_end": "2023-12-31", "value": 0.80},
            {"fy_end": "2024-12-31", "value": 1.00},
        ],
    )
    result = build_analysis(financials, Decimal("50"))
    dividend = result["fundamentals"]["dividend"]
    assert dividend["pays"] is True
    assert dividend["per_share"] == 1.0
    assert dividend["yield_pct"] == 2.0  # 1.00 / 50
    assert dividend["payout_ratio_pct"] == 50.0  # 1.00 / 2.00 EPS
    assert dividend["growth_yoy_pct"] == 25.0  # 1.00 vs 0.80
    assert dividend["cagr_pct"] is not None
    titles = {catalyst["title"] for catalyst in result["catalysts"]}
    assert "Dividend income" in titles


def test_non_payer_has_no_dividend() -> None:
    financials = _financials(
        revenue=Decimal("500000000"),
        previous_revenue=Decimal("400000000"),
        net_income=Decimal("40000000"),
        shares_outstanding=Decimal("50000000"),
        eps=Decimal("0.80"),
        equity=Decimal("300000000"),
    )
    result = build_analysis(financials, Decimal("20"))
    assert result["fundamentals"]["dividend"]["pays"] is False
    assert result["fundamentals"]["dividend"]["yield_pct"] is None


def test_no_positive_financials_raises() -> None:
    with pytest.raises(ValueError):
        build_analysis(_financials(), Decimal("10"))


def test_negative_equity_is_flagged_as_risk() -> None:
    financials = _financials(
        revenue=Decimal("500000000"),
        previous_revenue=Decimal("600000000"),
        net_income=Decimal("-50000000"),
        shares_outstanding=Decimal("50000000"),
        equity=Decimal("-100000000"),
        cash=Decimal("10000000"),
        debt=Decimal("200000000"),
    )

    result = build_analysis(financials, Decimal("4"))

    titles = {risk["title"] for risk in result["risks"]}
    assert "Negative shareholder equity" in titles
    assert "Revenue contraction" in titles
    assert result["risk_level"] == "High"


def test_implausible_upside_is_rejected() -> None:
    # Tiny share count (a dual-class / units error) yields absurd per-share value.
    financials = _financials(
        revenue=Decimal("6000000000"),
        previous_revenue=Decimal("5000000000"),
        net_income=Decimal("800000000"),
        free_cash_flow=Decimal("700000000"),
        cash=Decimal("1000000000"),
        debt=Decimal("200000000"),
        shares_outstanding=Decimal("10000"),  # implausibly small
        eps=Decimal("5.0"),
        equity=Decimal("4000000000"),
    )
    with pytest.raises(ValueError, match="Implausible"):
        build_analysis(financials, Decimal("200"))
