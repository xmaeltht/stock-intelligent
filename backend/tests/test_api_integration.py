"""End-to-end API checks against an in-memory database."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.analysis.factors import build_factor_scores
from app.analysis.technicals import build_technical_indicators
from app.analysis.valuation import EMPTY_FINANCIALS, build_analysis
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Company, StockAnalysis


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    _seed(session_factory)
    # https base_url so the Secure auth session cookie is retained across calls.
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def _seed(session_factory) -> None:
    history = [
        {
            "date": f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
            "open": 9.5 + index * 0.05,
            "high": 10.2 + index * 0.05,
            "low": 9.3 + index * 0.05,
            "close": 10.0 + index * 0.05,
            "volume": 500_000 + index * 1000,
        }
        for index in range(120)
    ]
    indicators = build_technical_indicators(history)
    financials = dict(EMPTY_FINANCIALS)
    financials.update(
        {
            "revenue": Decimal("500000000"),
            "previous_revenue": Decimal("400000000"),
            "net_income": Decimal("60000000"),
            "free_cash_flow": Decimal("50000000"),
            "cash": Decimal("120000000"),
            "debt": Decimal("40000000"),
            "shares_outstanding": Decimal("50000000"),
            "eps": Decimal("1.2"),
            "equity": Decimal("300000000"),
            "operating_income": Decimal("80000000"),
            "gross_profit": Decimal("250000000"),
            "revenue_history": [
                {"fy_end": "2023-12-31", "value": 300000000.0},
                {"fy_end": "2024-12-31", "value": 400000000.0},
                {"fy_end": "2025-12-31", "value": 500000000.0},
            ],
            "net_income_history": [
                {"fy_end": "2024-12-31", "value": 40000000.0},
                {"fy_end": "2025-12-31", "value": 60000000.0},
            ],
        }
    )
    result = build_analysis(financials, Decimal("15.95"))
    factor_scores = build_factor_scores(
        upside_pct=result["upside_pct"],
        indicators=indicators,
        fundamentals=result["fundamentals"],
        dividend={},
        net_income=60000000.0,
        free_cash_flow=50000000.0,
        cash=120000000.0,
        debt=40000000.0,
        equity=300000000.0,
        revenue_growth_pct=result["revenue_growth_pct"],
        price=15.95,
    )
    with session_factory() as session:
        company = Company(
            ticker="TEST", name="Test Corp", exchange="Nasdaq", cik="0000000001",
            sector="Technology",
        )
        session.add(company)
        session.flush()
        session.add(
            StockAnalysis(
                company_id=company.id,
                as_of=datetime.now(UTC),
                price_date=date(2026, 7, 10),
                current_price=Decimal("15.95"),
                volume=619_000,
                price_history=history,
                technical_indicators=indicators,
                revenue=financials["revenue"],
                previous_revenue=financials["previous_revenue"],
                net_income=financials["net_income"],
                free_cash_flow=financials["free_cash_flow"],
                cash=financials["cash"],
                debt=financials["debt"],
                shares_outstanding=financials["shares_outstanding"],
                eps=financials["eps"],
                factor_scores=factor_scores,
                sources=[{"name": "SEC", "url": "https://example.com"}],
                **result,
            )
        )
        session.commit()


def test_research_endpoints_respond(client: TestClient) -> None:
    for path in (
        "/api/v1/opportunities/summary",
        "/api/v1/opportunities/list?min_upside=-100",
        "/api/v1/opportunities/list?min_upside=-100&signal=Bullish",
        "/api/v1/opportunities/overview",
        "/api/v1/opportunities/stocks/TEST",
        "/api/v1/opportunities/stocks/TEST/history",
        "/api/v1/opportunities/compare?tickers=TEST,FAKE",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text[:300])


def test_paper_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/paper").status_code == 401


def _register(client: TestClient, email: str = "watcher@example.com") -> None:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1"})
    assert resp.status_code == 201, resp.text


def test_list_payload_stays_lean(client: TestClient) -> None:
    row = client.get("/api/v1/opportunities/list?min_upside=-100").json()[0]
    assert "price_history" not in row
    assert row["technical_indicators"]["signal"]


def test_detail_includes_fundamentals_and_new_technicals(client: TestClient) -> None:
    detail = client.get("/api/v1/opportunities/stocks/TEST").json()
    assert detail["fundamentals"]["ratios"]["price_to_earnings"] is not None
    assert detail["fundamentals"]["revenue_history"]
    assert detail["technical_indicators"]["bb_upper"] is not None
    assert len(detail["technical_indicators"]["checks"]) == 6


def test_watchlist_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/watchlist").status_code == 401
    assert client.post("/api/v1/watchlist/TEST").status_code == 401


def test_watchlist_round_trip(client: TestClient) -> None:
    _register(client)
    assert client.post("/api/v1/watchlist/TEST").status_code == 201
    rows = client.get("/api/v1/watchlist").json()
    assert rows and rows[0]["ticker"] == "TEST" and rows[0]["latest"]
    assert client.get("/api/v1/watchlist/tickers").json() == ["TEST"]
    watched = client.get("/api/v1/opportunities/list?watched_only=true&min_upside=-100").json()
    assert len(watched) == 1
    assert client.delete("/api/v1/watchlist/TEST").status_code == 200
    assert client.get("/api/v1/watchlist/tickers").json() == []


def test_watchlist_is_per_user(client: TestClient) -> None:
    _register(client, "a@example.com")
    assert client.post("/api/v1/watchlist/TEST").status_code == 201
    assert client.get("/api/v1/watchlist/tickers").json() == ["TEST"]
    # A different account starts with an empty watchlist.
    client.post("/api/v1/auth/logout")
    _register(client, "b@example.com")
    assert client.get("/api/v1/watchlist/tickers").json() == []


def test_unknown_watchlist_ticker_is_rejected(client: TestClient) -> None:
    _register(client)
    assert client.post("/api/v1/watchlist/NOPE").status_code == 404


def test_paper_portfolio_plan_and_trade_journal(client: TestClient) -> None:
    _register(client)
    initial = client.get("/api/v1/paper").json()
    assert initial["total_value"] == "100000.00"
    plan = client.post(
        "/api/v1/paper/plan",
        json={
            "ticker": "TEST",
            "entry_price": 15.95,
            "invalidation_price": 14,
            "target_price": 22,
        },
    )
    assert plan.status_code == 200, plan.text
    assert float(plan.json()["suggested_shares"]) > 0
    bought = client.post(
        "/api/v1/paper/trades",
        json={
            "ticker": "TEST",
            "side": "BUY",
            "quantity": 10,
            "price": 15,
            "invalidation_price": 14,
            "target_price": 22,
            "thesis": "Test thesis",
        },
    )
    assert bought.status_code == 201, bought.text
    payload = bought.json()
    assert payload["positions"][0]["ticker"] == "TEST"
    assert payload["positions"][0]["quantity"] == "10.000000"
    sold = client.post(
        "/api/v1/paper/trades",
        json={"ticker": "TEST", "side": "SELL", "quantity": 4, "price": 20},
    )
    assert sold.status_code == 201, sold.text
    result = sold.json()
    assert result["positions"][0]["quantity"] == "6.000000"
    assert result["trades"][0]["realized_pnl"] == "20.00"


def test_paper_portfolio_rejects_overselling(client: TestClient) -> None:
    _register(client)
    response = client.post(
        "/api/v1/paper/trades",
        json={"ticker": "TEST", "side": "SELL", "quantity": 1, "price": 15},
    )
    assert response.status_code == 409


def test_paper_portfolio_is_per_user(client: TestClient) -> None:
    _register(client, "trader1@example.com")
    client.post(
        "/api/v1/paper/trades",
        json={"ticker": "TEST", "side": "BUY", "quantity": 5, "price": 15},
    )
    assert client.get("/api/v1/paper").json()["positions"][0]["ticker"] == "TEST"
    # A second account gets a fresh, empty portfolio.
    client.post("/api/v1/auth/logout")
    _register(client, "trader2@example.com")
    second = client.get("/api/v1/paper").json()
    assert second["positions"] == []
    assert second["cash_balance"] == "100000.00"


def test_failure_summary_groups_errors(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/failures")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_failed"] == 0
    assert payload["top_errors"] == []


def test_requeue_failures_clears_cooldowns(client: TestClient) -> None:
    response = client.post("/api/v1/opportunities/requeue-failures")
    assert response.status_code == 200
    assert response.json() == {"scope": "failures", "requeued": 0}


def test_requeue_stale_targets_pre_pipeline_analyses(client: TestClient) -> None:
    # The seeded analysis has volume set, so nothing is stale.
    response = client.post("/api/v1/opportunities/requeue-failures?scope=stale")
    assert response.status_code == 200
    assert response.json() == {"scope": "stale", "requeued": 0}
    # scope=all touches every company (exactly one is seeded).
    response = client.post("/api/v1/opportunities/requeue-failures?scope=all")
    assert response.json() == {"scope": "all", "requeued": 1}


def test_search_ignores_upside_threshold(client: TestClient) -> None:
    # A high threshold would exclude a 0%-upside name, but a matching search
    # must still return it.
    with_search = client.get(
        "/api/v1/opportunities/list?search=Test&min_upside=95"
    ).json()
    assert any(row["company"]["ticker"] == "TEST" for row in with_search)


def test_search_ignores_asset_type_toggle(client: TestClient) -> None:
    # Seeded TEST is a Stock; searching it while the ETF toggle is active must
    # still find it, so a searched ticker is never hidden by the type filter.
    rows = client.get(
        "/api/v1/opportunities/list?search=TEST&asset_type=ETF&min_upside=-100"
    ).json()
    assert any(row["company"]["ticker"] == "TEST" for row in rows)


def test_list_sorts_by_new_keys(client: TestClient) -> None:
    for key in (
        "rating", "change_1d", "change_5d", "signal", "rsi", "confidence", "risk",
        "factor_composite", "factor_value", "factor_quality", "factor_momentum",
    ):
        response = client.get(
            f"/api/v1/opportunities/list?min_upside=-100&sort_by={key}&sort_order=desc"
        )
        assert response.status_code == 200, (key, response.text[:200])
        assert response.json(), key


def test_factor_scores_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/stocks/TEST/factors")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sector"] == "Technology"
    assert set(payload["scores"]) >= {
        "value", "quality", "momentum", "growth", "income", "composite",
    }
    # Sole security in its sector → 100th percentile on every factor it scores.
    assert payload["sector_percentiles"]["composite"] == 100


def test_list_includes_factor_scores(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/list?min_upside=-100")
    assert response.status_code == 200
    rows = response.json()
    assert rows and "factor_scores" in rows[0]
    assert "composite" in rows[0]["factor_scores"]


def test_screen_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/screen?q=technology stocks under $50")
    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["sector"] == "Technology"
    assert payload["filters"]["max_price"] == 50
    assert "results" in payload and "interpretation" in payload
    assert isinstance(payload["count"], int)


def test_sector_factors_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/sector-factors")
    assert response.status_code == 200
    payload = response.json()
    assert "sectors" in payload
    assert payload["factors"] == ["value", "quality", "momentum", "growth", "income", "composite"]


def test_radar_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/radar")
    assert response.status_code == 200
    payload = response.json()
    assert "categories" in payload and "total_events" in payload
    keys = {cat["key"] for cat in payload["categories"]}
    assert {"golden_cross", "unusual_volume", "gainers", "value", "momentum"} <= keys


def test_backtest_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/backtest")
    assert response.status_code == 200
    payload = response.json()
    assert "ratings" in payload and "benchmark" in payload
    assert {"rating", "by_horizon"} <= set(payload["ratings"][0])
    assert [h["label"] for h in payload["horizons"]] == ["1M", "3M", "6M"]


def test_ideas_endpoint_returns_two_lists(client: TestClient) -> None:
    response = client.get("/api/v1/opportunities/ideas")
    assert response.status_code == 200
    payload = response.json()
    assert "swing" in payload and "long_term" in payload
    assert isinstance(payload["swing"], list)
    assert isinstance(payload["long_term"], list)
