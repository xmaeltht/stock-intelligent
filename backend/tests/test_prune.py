from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.jobs.daily_pipeline import prune_company_snapshots
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _analysis(company_id, index):
    return StockAnalysis(
        company_id=company_id,
        as_of=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index),
        price_date=datetime(2026, 1, 1).date(),
        current_price=Decimal("10"),
        price_history=[{"date": "2026-01-01", "close": 10}],
        technical_indicators={},
        factor_scores={},
        fair_value=Decimal("12"),
        bear_value=Decimal("8"),
        bull_value=Decimal("15"),
        upside_pct=20.0,
        opportunity_score=50,
        confidence_grade="B",
        risk_level="Low",
        qualification="ok",
    )


def _all(session):
    return list(session.scalars(select(StockAnalysis).order_by(StockAnalysis.as_of.desc())))


def test_prune_caps_and_strips_history() -> None:
    session = _session()
    company = Company(ticker="TEST", name="Test", exchange="Nasdaq", cik="0000000001")
    session.add(company)
    session.flush()
    for index in range(10):
        session.add(_analysis(company.id, index))
    session.flush()

    prune_company_snapshots(session, company.id, keep=3)
    session.commit()

    rows = _all(session)
    assert len(rows) == 3  # capped to retention window
    assert rows[0].price_history == [{"date": "2026-01-01", "close": 10}]  # newest keeps history
    assert rows[1].price_history == []  # superseded row stripped


def test_prune_noop_with_single_snapshot() -> None:
    session = _session()
    company = Company(ticker="ONE", name="One", exchange="Nasdaq", cik="0000000002")
    session.add(company)
    session.flush()
    session.add(_analysis(company.id, 0))
    session.flush()

    prune_company_snapshots(session, company.id, keep=3)
    session.commit()

    rows = _all(session)
    assert len(rows) == 1
    assert rows[0].price_history == [{"date": "2026-01-01", "close": 10}]
