import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert import AlertEvent, AlertRule
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.models.user import User
from app.schemas.alerts import AlertEventRead, AlertRuleCreate, AlertRuleRead
from app.services.alerts import condition_met, evaluate_alerts

router = APIRouter()


def _rule_read(rule: AlertRule, company: Company) -> AlertRuleRead:
    return AlertRuleRead(
        id=rule.id,
        ticker=company.ticker,
        name=company.name,
        kind=rule.kind,
        threshold=Decimal(rule.threshold),
        active=rule.active,
        created_at=rule.created_at,
    )


def _event_read(event: AlertEvent) -> AlertEventRead:
    return AlertEventRead(
        id=event.id,
        ticker=event.company.ticker,
        name=event.company.name,
        kind=event.kind,
        message=event.message,
        price_at=Decimal(event.price_at) if event.price_at is not None else None,
        created_at=event.created_at,
        read_at=event.read_at,
    )


@router.get("", response_model=list[AlertRuleRead])
def list_rules(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[AlertRuleRead]:
    rules = db.scalars(
        select(AlertRule)
        .options(joinedload(AlertRule.company))
        .where(AlertRule.user_id == user.id)
        .order_by(AlertRule.created_at.desc())
    )
    return [_rule_read(rule, rule.company) for rule in rules]


@router.post("", response_model=AlertRuleRead, status_code=201)
def create_rule(
    payload: AlertRuleCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AlertRuleRead:
    company = db.scalar(select(Company).where(Company.ticker == payload.ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Unknown ticker")
    rule = AlertRule(
        user_id=user.id,
        company_id=company.id,
        kind=payload.kind,
        threshold=payload.threshold,
    )
    # Seed last_state from the current reading so an already-true condition does
    # not fire immediately — only a fresh crossing should notify.
    analysis = db.scalar(
        select(StockAnalysis).where(
            StockAnalysis.company_id == company.id, StockAnalysis.is_current.is_(True)
        )
    )
    if analysis is not None:
        rule.last_state, _ = condition_met(payload.kind, payload.threshold, analysis)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_read(rule, company)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    rule = db.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
    )
    if rule is not None:
        db.delete(rule)
        db.commit()


@router.get("/events", response_model=list[AlertEventRead])
def list_events(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[AlertEventRead]:
    evaluate_alerts(db, user)
    events = db.scalars(
        select(AlertEvent)
        .options(joinedload(AlertEvent.company))
        .where(AlertEvent.user_id == user.id)
        .order_by(AlertEvent.created_at.desc())
        .limit(50)
    )
    return [_event_read(event) for event in events]


@router.get("/unread-count", response_model=dict)
def unread_count(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    evaluate_alerts(db, user)
    total = (
        db.scalar(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.user_id == user.id, AlertEvent.read_at.is_(None))
        )
        or 0
    )
    return {"count": total}


@router.post("/read", response_model=dict)
def mark_read(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    db.execute(
        update(AlertEvent)
        .where(AlertEvent.user_id == user.id, AlertEvent.read_at.is_(None))
        .values(read_at=func.now())
    )
    db.commit()
    return {"ok": True}
