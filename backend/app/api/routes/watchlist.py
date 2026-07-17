from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, load_only

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.company import Company
from app.models.stock_analysis import StockAnalysis
from app.models.user import User
from app.models.watchlist import WatchlistEntry
from app.schemas.analysis import AnalysisListItem, WatchlistItem
from app.services.queries import latest_ids
from app.services.screener import LIST_COLUMNS

router = APIRouter()


class WatchlistUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get("", response_model=list[WatchlistItem])
def list_watchlist(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[WatchlistItem]:
    entries = list(
        db.scalars(
            select(WatchlistEntry)
            .options(joinedload(WatchlistEntry.company))
            .where(WatchlistEntry.user_id == user.id)
            .order_by(WatchlistEntry.created_at.desc())
        )
    )
    if not entries:
        return []
    company_ids = [entry.company_id for entry in entries]
    analyses = {
        analysis.company_id: analysis
        for analysis in db.scalars(
            select(StockAnalysis)
            .options(load_only(*LIST_COLUMNS), joinedload(StockAnalysis.company))
            .where(
                StockAnalysis.id.in_(latest_ids()),
                StockAnalysis.company_id.in_(company_ids),
            )
        )
    }
    return [
        WatchlistItem(
            ticker=entry.company.ticker,
            name=entry.company.name,
            exchange=entry.company.exchange,
            asset_type=entry.company.asset_type,
            note=entry.note,
            created_at=entry.created_at,
            latest=(
                AnalysisListItem.model_validate(analyses[entry.company_id])
                if entry.company_id in analyses
                else None
            ),
        )
        for entry in entries
    ]


@router.get("/tickers", response_model=list[str])
def watchlist_tickers(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[str]:
    return list(
        db.scalars(
            select(Company.ticker)
            .join(WatchlistEntry, WatchlistEntry.company_id == Company.id)
            .where(WatchlistEntry.user_id == user.id)
            .order_by(Company.ticker)
        )
    )


@router.post("/{ticker}", response_model=dict, status_code=201)
def add_to_watchlist(
    ticker: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: WatchlistUpdate | None = None,
) -> dict:
    company = db.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Unknown ticker")
    entry = db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.company_id == company.id,
            WatchlistEntry.user_id == user.id,
        )
    )
    if entry is None:
        entry = WatchlistEntry(company_id=company.id, user_id=user.id)
        db.add(entry)
    if payload is not None:
        entry.note = payload.note
    db.commit()
    return {"ticker": company.ticker, "watchlisted": True}


@router.delete("/{ticker}", response_model=dict)
def remove_from_watchlist(
    ticker: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    company = db.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Unknown ticker")
    entry = db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.company_id == company.id,
            WatchlistEntry.user_id == user.id,
        )
    )
    if entry is not None:
        db.delete(entry)
        db.commit()
    return {"ticker": company.ticker, "watchlisted": False}
