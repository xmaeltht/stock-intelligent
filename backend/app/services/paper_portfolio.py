from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.company import Company
from app.models.paper_portfolio import PaperPortfolio, PaperTrade
from app.models.stock_analysis import StockAnalysis
from app.schemas.paper import PaperTradeCreate, RiskPlanCreate

MONEY = Decimal("0.01")
SHARES = Decimal("0.000001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY)


def get_or_create_portfolio(db: Session) -> PaperPortfolio:
    portfolio = db.scalar(select(PaperPortfolio).order_by(PaperPortfolio.created_at).limit(1))
    if portfolio is None:
        portfolio = PaperPortfolio(
            name="My paper portfolio",
            starting_cash=Decimal("100000"),
            cash_balance=Decimal("100000"),
            max_risk_per_trade_pct=1.0,
            max_position_pct=10.0,
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
    return portfolio


def _trades(db: Session, portfolio: PaperPortfolio) -> list[PaperTrade]:
    return list(
        db.scalars(
            select(PaperTrade)
            .options(joinedload(PaperTrade.company))
            .where(PaperTrade.portfolio_id == portfolio.id)
            .order_by(PaperTrade.executed_at, PaperTrade.id)
        )
    )


def _position_state(trades: list[PaperTrade]) -> tuple[dict, Decimal]:
    positions: dict = {}
    realized = Decimal("0")
    for trade in trades:
        state = positions.setdefault(
            trade.company_id,
            {
                "company": trade.company,
                "quantity": Decimal("0"),
                "average_cost": Decimal("0"),
                "target_price": None,
                "invalidation_price": None,
            },
        )
        quantity = Decimal(trade.quantity)
        price = Decimal(trade.price)
        fees = Decimal(trade.fees or 0)
        if trade.side == "BUY":
            prior_cost = state["quantity"] * state["average_cost"]
            next_quantity = state["quantity"] + quantity
            state["average_cost"] = (prior_cost + quantity * price + fees) / next_quantity
            state["quantity"] = next_quantity
            state["target_price"] = trade.target_price or state["target_price"]
            state["invalidation_price"] = (
                trade.invalidation_price or state["invalidation_price"]
            )
        else:
            state["quantity"] -= quantity
            realized += Decimal(trade.realized_pnl or 0)
            if state["quantity"] <= 0:
                state["quantity"] = Decimal("0")
                state["average_cost"] = Decimal("0")
    return positions, realized


def build_portfolio(db: Session) -> dict:
    portfolio = get_or_create_portfolio(db)
    trades = _trades(db, portfolio)
    state, realized = _position_state(trades)
    held_ids = [company_id for company_id, item in state.items() if item["quantity"] > 0]
    latest = {
        row.company_id: Decimal(row.current_price)
        for row in db.scalars(
            select(StockAnalysis).where(
                StockAnalysis.is_current.is_(True),
                StockAnalysis.company_id.in_(held_ids),
            )
        )
    }
    position_rows = []
    invested = Decimal("0")
    cost_basis_total = Decimal("0")
    for company_id, item in state.items():
        quantity = item["quantity"]
        if quantity <= 0:
            continue
        current = latest.get(company_id, item["average_cost"])
        market_value = quantity * current
        cost_basis = quantity * item["average_cost"]
        invested += market_value
        cost_basis_total += cost_basis
        position_rows.append((item, current, market_value, cost_basis))
    total_value = Decimal(portfolio.cash_balance) + invested
    positions = []
    for item, current, market_value, cost_basis in position_rows:
        unrealized = market_value - cost_basis
        positions.append(
            {
                "ticker": item["company"].ticker,
                "name": item["company"].name,
                "quantity": item["quantity"].quantize(SHARES),
                "average_cost": _money(item["average_cost"]),
                "current_price": _money(current),
                "market_value": _money(market_value),
                "cost_basis": _money(cost_basis),
                "unrealized_pnl": _money(unrealized),
                "unrealized_pct": (
                    round(float(unrealized / cost_basis * 100), 2) if cost_basis else 0
                ),
                "allocation_pct": (
                    round(float(market_value / total_value * 100), 2)
                    if total_value
                    else 0
                ),
                "target_price": item["target_price"],
                "invalidation_price": item["invalidation_price"],
            }
        )
    positions.sort(key=lambda item: item["market_value"], reverse=True)
    total_return = total_value - Decimal(portfolio.starting_cash)
    return {
        "id": str(portfolio.id),
        "name": portfolio.name,
        "starting_cash": _money(Decimal(portfolio.starting_cash)),
        "cash_balance": _money(Decimal(portfolio.cash_balance)),
        "total_value": _money(total_value),
        "invested_value": _money(invested),
        "total_return": _money(total_return),
        "total_return_pct": round(
            float(total_return / Decimal(portfolio.starting_cash) * 100), 2
        ),
        "realized_pnl": _money(realized),
        "unrealized_pnl": _money(invested - cost_basis_total),
        "max_risk_per_trade_pct": portfolio.max_risk_per_trade_pct,
        "max_position_pct": portfolio.max_position_pct,
        "positions": positions,
        "trades": [
            {
                "id": str(trade.id),
                "ticker": trade.company.ticker,
                "name": trade.company.name,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": trade.price,
                "fees": trade.fees,
                "realized_pnl": trade.realized_pnl,
                "thesis": trade.thesis,
                "catalyst": trade.catalyst,
                "invalidation_price": trade.invalidation_price,
                "target_price": trade.target_price,
                "notes": trade.notes,
                "executed_at": trade.executed_at,
            }
            for trade in reversed(trades)
        ],
    }


def execute_trade(db: Session, payload: PaperTradeCreate) -> PaperTrade:
    portfolio = get_or_create_portfolio(db)
    company = db.scalar(select(Company).where(Company.ticker == payload.ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Unknown ticker")
    analysis = db.scalar(
        select(StockAnalysis).where(
            StockAnalysis.company_id == company.id,
            StockAnalysis.is_current.is_(True),
        )
    )
    if payload.price is None and analysis is None:
        raise HTTPException(status_code=409, detail="No current price is available")
    price = Decimal(payload.price or analysis.current_price)
    quantity = Decimal(payload.quantity)
    fees = Decimal(payload.fees)
    state, _ = _position_state(_trades(db, portfolio))
    held = state.get(company.id, {}).get("quantity", Decimal("0"))
    realized_pnl = None
    if payload.side == "BUY":
        required = quantity * price + fees
        if required > Decimal(portfolio.cash_balance):
            raise HTTPException(status_code=409, detail="Insufficient paper cash")
        portfolio.cash_balance = Decimal(portfolio.cash_balance) - required
    else:
        if quantity > held:
            raise HTTPException(status_code=409, detail=f"Only {held} shares are available")
        if quantity * price < fees:
            raise HTTPException(status_code=422, detail="Fees exceed sale proceeds")
        average_cost = state[company.id]["average_cost"]
        realized_pnl = _money((price - average_cost) * quantity - fees)
        portfolio.cash_balance = Decimal(portfolio.cash_balance) + quantity * price - fees
    trade = PaperTrade(
        portfolio_id=portfolio.id,
        company_id=company.id,
        side=payload.side,
        quantity=quantity,
        price=price,
        fees=fees,
        realized_pnl=realized_pnl,
        thesis=payload.thesis,
        catalyst=payload.catalyst,
        invalidation_price=payload.invalidation_price,
        target_price=payload.target_price,
        notes=payload.notes,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def build_risk_plan(db: Session, payload: RiskPlanCreate) -> dict:
    portfolio = get_or_create_portfolio(db)
    company = db.scalar(select(Company).where(Company.ticker == payload.ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Unknown ticker")
    analysis = db.scalar(
        select(StockAnalysis).where(
            StockAnalysis.company_id == company.id,
            StockAnalysis.is_current.is_(True),
        )
    )
    if payload.entry_price is None and analysis is None:
        raise HTTPException(status_code=409, detail="No current price is available")
    entry = Decimal(payload.entry_price or analysis.current_price)
    stop = Decimal(payload.invalidation_price)
    if stop >= entry:
        raise HTTPException(status_code=422, detail="Invalidation price must be below entry")
    summary = build_portfolio(db)
    total_value = Decimal(summary["total_value"])
    risk_pct = payload.risk_pct or portfolio.max_risk_per_trade_pct
    risk_budget = total_value * Decimal(str(risk_pct)) / 100
    risk_per_share = entry - stop
    by_risk = risk_budget / risk_per_share
    position_cap = total_value * Decimal(str(portfolio.max_position_pct)) / 100
    by_position = position_cap / entry
    by_cash = Decimal(portfolio.cash_balance) / entry
    suggested = min(by_risk, by_position, by_cash).quantize(SHARES, rounding=ROUND_DOWN)
    position_value = suggested * entry
    warnings: list[str] = []
    if suggested == by_cash.quantize(SHARES, rounding=ROUND_DOWN):
        warnings.append("Available cash limits this position")
    if suggested == by_position.quantize(SHARES, rounding=ROUND_DOWN):
        warnings.append("Maximum position allocation limits this position")
    target = Decimal(payload.target_price) if payload.target_price is not None else None
    reward_risk = float((target - entry) / risk_per_share) if target and target > entry else None
    if reward_risk is not None and reward_risk < 2:
        warnings.append("Reward/risk is below 2:1")
    return {
        "ticker": company.ticker,
        "portfolio_value": _money(total_value),
        "entry_price": _money(entry),
        "invalidation_price": _money(stop),
        "target_price": _money(target) if target else None,
        "risk_pct": risk_pct,
        "risk_budget": _money(risk_budget),
        "risk_per_share": _money(risk_per_share),
        "suggested_shares": suggested,
        "suggested_position_value": _money(position_value),
        "position_pct": round(float(position_value / total_value * 100), 2) if total_value else 0,
        "reward_risk_ratio": round(reward_risk, 2) if reward_risk is not None else None,
        "warnings": warnings,
    }
