from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.paper_portfolio import PaperTrade
from app.models.user import User
from app.schemas.paper import (
    PaperPortfolioRead,
    PaperPortfolioUpdate,
    PaperTradeCreate,
    RiskPlanCreate,
    RiskPlanRead,
)
from app.services.paper_portfolio import (
    build_portfolio,
    build_risk_plan,
    execute_trade,
    get_or_create_portfolio,
)

router = APIRouter()


@router.get("", response_model=PaperPortfolioRead)
def portfolio(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return build_portfolio(db, user)


@router.put("/settings", response_model=PaperPortfolioRead)
def update_settings(
    payload: PaperPortfolioUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    portfolio = get_or_create_portfolio(db, user)
    if payload.name is not None:
        portfolio.name = payload.name
    if payload.starting_cash is not None:
        trade_count = db.scalar(
            select(func.count()).select_from(PaperTrade).where(
                PaperTrade.portfolio_id == portfolio.id
            )
        ) or 0
        if trade_count:
            raise HTTPException(status_code=409, detail="Starting cash cannot change after trading")
        portfolio.starting_cash = Decimal(payload.starting_cash)
        portfolio.cash_balance = Decimal(payload.starting_cash)
    if payload.max_risk_per_trade_pct is not None:
        portfolio.max_risk_per_trade_pct = payload.max_risk_per_trade_pct
    if payload.max_position_pct is not None:
        portfolio.max_position_pct = payload.max_position_pct
    db.commit()
    return build_portfolio(db, user)


@router.post("/plan", response_model=RiskPlanRead)
def risk_plan(
    payload: RiskPlanCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return build_risk_plan(db, payload, user)


@router.post("/trades", response_model=PaperPortfolioRead, status_code=201)
def trade(
    payload: PaperTradeCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    execute_trade(db, payload, user)
    return build_portfolio(db, user)
