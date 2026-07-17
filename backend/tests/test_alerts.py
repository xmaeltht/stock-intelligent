from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.alert import AlertEvent, AlertRule
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.models.user import User
from app.services.alerts import evaluate_alerts


def _analysis(company_id, price, upside):
    return StockAnalysis(
        company_id=company_id,
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        price_date=datetime(2026, 1, 1).date(),
        current_price=Decimal(str(price)),
        price_history=[],
        technical_indicators={},
        factor_scores={},
        fair_value=Decimal("20"),
        bear_value=Decimal("10"),
        bull_value=Decimal("25"),
        upside_pct=upside,
        opportunity_score=50,
        confidence_grade="B",
        risk_level="Low",
        qualification="ok",
        is_current=True,
    )


def _setup(price=15.95, upside=30.0):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(email="a@b.com", password_hash="x")
    company = Company(ticker="TEST", name="Test", exchange="Nasdaq", cik="0000000001")
    session.add_all([user, company])
    session.flush()
    session.add(_analysis(company.id, price, upside))
    session.commit()
    return session, user, company


def _rule(session, user, company, kind, threshold):
    rule = AlertRule(
        user_id=user.id,
        company_id=company.id,
        kind=kind,
        threshold=Decimal(str(threshold)),
        last_state=False,
    )
    session.add(rule)
    session.commit()
    return rule


def _events(session):
    return list(session.scalars(select(AlertEvent)))


def test_price_below_fires_once_on_crossing() -> None:
    session, user, company = _setup(price=15.95)
    rule = _rule(session, user, company, "price_below", 20)
    assert evaluate_alerts(session, user) == 1
    events = _events(session)
    assert len(events) == 1
    assert "below" in events[0].message and "TEST" in events[0].message
    session.refresh(rule)
    assert rule.last_state is True
    # Stays true → does not re-fire.
    assert evaluate_alerts(session, user) == 0
    assert len(_events(session)) == 1


def test_upside_above_fires() -> None:
    session, user, company = _setup(upside=30.0)
    _rule(session, user, company, "upside_above", 20)
    assert evaluate_alerts(session, user) == 1
    assert "upside" in _events(session)[0].message


def test_condition_not_met_creates_no_event() -> None:
    session, user, company = _setup(price=15.95)
    _rule(session, user, company, "price_above", 20)  # 15.95 is not above 20
    assert evaluate_alerts(session, user) == 0
    assert _events(session) == []
