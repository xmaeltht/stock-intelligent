from app.analysis.factors import build_factor_scores


def _base(**over):
    args = dict(
        upside_pct=0.0,
        indicators={},
        fundamentals={},
        dividend={},
        net_income=None,
        free_cash_flow=None,
        cash=None,
        debt=None,
        equity=None,
        revenue_growth_pct=None,
        price=100.0,
    )
    args.update(over)
    return args


def test_scores_are_bounded_0_100() -> None:
    scores = build_factor_scores(**_base())
    for key, value in scores.items():
        assert 0.0 <= value <= 100.0, (key, value)


def test_high_quality_growth_company_scores_well() -> None:
    scores = build_factor_scores(
        **_base(
            upside_pct=60.0,
            indicators={"change_20d_pct": 12, "change_5d_pct": 4, "sma50": 90, "sma200": 80,
                        "rsi14": 62, "trend_cross": "Golden cross"},
            fundamentals={
                "ratios": {"price_to_earnings": 12, "price_to_sales": 2, "price_to_fcf": 14},
                "margins": {"net_pct": 22, "operating_pct": 28, "fcf_pct": 20},
                "revenue_cagr_pct": 18,
                "net_income_history": [{"value": 100}, {"value": 130}],
            },
            dividend={"pays": True, "yield_pct": 1.5, "shareholder_yield_pct": 3.5,
                      "growth_streak_years": 5, "payout_ratio_pct": 30},
            net_income=150.0, free_cash_flow=120.0, cash=300.0, debt=100.0, equity=900.0,
            revenue_growth_pct=20.0, price=100.0,
        )
    )
    assert scores["quality"] >= 70
    assert scores["momentum"] >= 60
    assert scores["growth"] >= 60
    assert scores["composite"] >= 60


def test_weak_company_scores_low() -> None:
    scores = build_factor_scores(
        **_base(
            upside_pct=-40.0,
            indicators={"change_20d_pct": -18, "change_5d_pct": -6, "sma50": 120, "sma200": 140,
                        "rsi14": 28, "trend_cross": "Death cross"},
            fundamentals={"ratios": {"price_to_earnings": 45, "price_to_sales": 12},
                          "margins": {"net_pct": -15, "operating_pct": -8}},
            net_income=-50.0, free_cash_flow=-20.0, cash=10.0, debt=200.0, equity=-100.0,
            revenue_growth_pct=-12.0, price=100.0,
        )
    )
    assert scores["momentum"] <= 40
    assert scores["quality"] <= 40
    assert scores["value"] <= 45


def test_non_payer_has_low_income_score() -> None:
    scores = build_factor_scores(**_base(dividend={"pays": False}))
    assert scores["income"] <= 35
