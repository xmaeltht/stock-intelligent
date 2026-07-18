"""Alert evaluation.

Rules are evaluated against each security's current analysis. An event fires
once when the condition transitions from false to true (a crossing), tracked via
`last_state`, so a rule that stays true doesn't spam the feed.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.alert import AlertEvent, AlertRule
from app.models.stock_analysis import StockAnalysis
from app.models.user import User


def condition_met(kind: str, threshold: Decimal, analysis: StockAnalysis) -> tuple[bool, Decimal]:
    """Return (met, current_price) for a rule against a current analysis."""
    price = Decimal(analysis.current_price)
    if kind == "price_below":
        return price < threshold, price
    if kind == "price_above":
        return price > threshold, price
    if kind == "upside_above":
        upside = analysis.upside_pct
        return (upside is not None and float(upside) > float(threshold)), price
    return False, price


def _message(kind: str, ticker: str, threshold: Decimal, analysis: StockAnalysis) -> str:
    price = Decimal(analysis.current_price)
    if kind == "price_below":
        return f"{ticker} dropped below ${threshold:.2f} — now ${price:.2f}"
    if kind == "price_above":
        return f"{ticker} rose above ${threshold:.2f} — now ${price:.2f}"
    upside = float(analysis.upside_pct or 0)
    return f"{ticker} upside crossed {float(threshold):.0f}% — now {upside:.1f}%"


def current_analyses(db: Session, company_ids: set) -> dict:
    if not company_ids:
        return {}
    return {
        analysis.company_id: analysis
        for analysis in db.scalars(
            select(StockAnalysis).where(
                StockAnalysis.is_current.is_(True),
                StockAnalysis.company_id.in_(company_ids),
            )
        )
    }


def _evaluate_rules(db: Session, rules: list[AlertRule]) -> int:
    """Fire events for any rule that just crossed into its met state."""
    if not rules:
        return 0
    analyses = current_analyses(db, {rule.company_id for rule in rules})
    created = 0
    dirty = False
    for rule in rules:
        analysis = analyses.get(rule.company_id)
        if analysis is None:
            continue
        met, price = condition_met(rule.kind, Decimal(rule.threshold), analysis)
        if met and not rule.last_state:
            message = _message(rule.kind, rule.company.ticker, Decimal(rule.threshold), analysis)
            db.add(
                AlertEvent(
                    user_id=rule.user_id,
                    company_id=rule.company_id,
                    kind=rule.kind,
                    message=message,
                    price_at=price,
                )
            )
            created += 1
        if met != rule.last_state:
            rule.last_state = met
            dirty = True
    if created or dirty:
        db.commit()
    return created


def evaluate_alerts(db: Session, user: User) -> int:
    """Evaluate one user's active rules (on-demand, when they're in the app)."""
    rules = list(
        db.scalars(
            select(AlertRule)
            .options(joinedload(AlertRule.company))
            .where(AlertRule.user_id == user.id, AlertRule.active.is_(True))
        )
    )
    return _evaluate_rules(db, rules)


def evaluate_all_active(db: Session) -> int:
    """Evaluate every user's active rules — the background pass, so alerts fire
    even when no one is looking. Returns the number of events created."""
    rules = list(
        db.scalars(
            select(AlertRule)
            .options(joinedload(AlertRule.company))
            .where(AlertRule.active.is_(True))
        )
    )
    return _evaluate_rules(db, rules)
