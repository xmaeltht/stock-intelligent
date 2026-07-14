from app.analysis.dividends import build_dividend_profile


def _quarterly_events() -> list[dict[str, object]]:
    return [
        {"date": "2024-03-15", "amount": 0.20},
        {"date": "2024-06-14", "amount": 0.20},
        {"date": "2024-09-13", "amount": 0.22},
        {"date": "2024-12-13", "amount": 0.22},
        {"date": "2025-03-14", "amount": 0.24},
        {"date": "2025-06-13", "amount": 0.24},
        {"date": "2025-09-12", "amount": 0.26},
        {"date": "2025-12-12", "amount": 0.26},
    ]


def test_quarterly_profile() -> None:
    profile = build_dividend_profile(
        _quarterly_events(),
        price=40.0,
        eps=4.0,
        market_cap=1_000_000_000.0,
        buyback_net=20_000_000.0,
    )
    assert profile["pays"] is True
    assert profile["frequency"] == "Quarterly"
    assert profile["payments_per_year"] == 4
    assert profile["last_ex_date"] == "2025-12-12"
    assert profile["last_amount"] == 0.26
    # forward run-rate = last payment * 4
    assert profile["forward_annual"] == 1.04
    assert profile["forward_yield_pct"] == 2.6  # 1.04 / 40
    assert len(profile["payments"]) == 8
    assert profile["payments"][0]["date"] == "2025-12-12"  # most recent first
    # buyback yield = 20M / 1B = 2%, shareholder yield = ttm yield + 2%
    assert profile["buyback_yield_pct"] == 2.0
    assert profile["shareholder_yield_pct"] is not None
    assert profile["growth_streak_years"] >= 1


def test_no_dividend() -> None:
    assert build_dividend_profile([], price=50.0) == {"pays": False}


def test_sec_only_fallback() -> None:
    profile = build_dividend_profile(
        [],
        price=100.0,
        eps=5.0,
        sec_annual_dps=[
            {"fy_end": "2023-12-31", "value": 2.0},
            {"fy_end": "2024-12-31", "value": 2.5},
        ],
    )
    assert profile["pays"] is True
    assert profile["annual_amount_ttm"] == 2.5
    assert profile["yield_pct"] == 2.5  # 2.5 / 100
    assert profile["payments"] == []
