import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    name: str
    exchange: str | None
    asset_type: str
    cik: str | None
    sector: str | None
    industry: str | None
    country: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
