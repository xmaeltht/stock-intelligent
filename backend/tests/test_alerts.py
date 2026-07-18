from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.alert import AlertEvent, AlertRule
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.models.user import User
from app.services.alerts import evaluate_alerts, evaluate_all_active


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


def test_evaluate_all_active_fires_for_every_user() -> None:
    session, user, company = _setup(price=15.95)
    user2 = User(email="c@d.com", password_hash="x")
    session.add(user2)
    session.flush()
    _rule(session, user, company, "price_below", 20)  # met
    session.add(
        AlertRule(
            user_id=user2.id,
            company_id=company.id,
            kind="price_below",
            threshold=Decimal("20"),
            last_state=False,
        )
    )
    session.commit()
    assert evaluate_all_active(session) == 2
    events = _events(session)
    assert len(events) == 2
    assert {event.user_id for event in events} == {user.id, user2.id}


def test_build_alert_email_formats() -> None:
    from app.services.alerts import build_alert_email

    event = AlertEvent(kind="price_below", message="TEST dropped below $20.00 — now $15.95")
    subject, body = build_alert_email([event])
    assert "1 new alert" in subject
    assert "TEST dropped below" in body
    assert "/alerts" in body


def test_dispatch_emails_only_pro_users() -> None:
    from app.services.alerts import dispatch_alert_emails

    session, user, company = _setup(price=15.95)
    user.plan = "pro"
    free = User(email="free@x.com", password_hash="x", plan="free")
    session.add(free)
    session.flush()
    session.add_all(
        [
            AlertEvent(
                user_id=user.id, company_id=company.id, kind="price_below", message="pro msg"
            ),
            AlertEvent(
                user_id=free.id, company_id=company.id, kind="price_below", message="free msg"
            ),
        ]
    )
    session.commit()

    sent: list = []
    count = dispatch_alert_emails(session, send=lambda to, s, b: sent.append(to))
    assert count == 1
    assert sent == [user.email]
    # Both events are marked processed; a second pass sends nothing.
    assert dispatch_alert_emails(session, send=lambda to, s, b: sent.append(to)) == 0
    assert sent == [user.email]
