from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.schemas.company import CompanyRead

router = APIRouter()


@router.get("", response_model=list[CompanyRead])
def list_companies(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Company]:
    statement = (
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.ticker)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))

