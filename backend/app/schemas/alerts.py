import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AlertKind = Literal["price_below", "price_above", "upside_above"]


class AlertRuleCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    kind: AlertKind
    threshold: Decimal = Field(gt=-1000, le=1_000_000)


class AlertRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    name: str
    kind: str
    threshold: Decimal
    active: bool
    created_at: datetime


class AlertEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    name: str
    kind: str
    message: str
    price_at: Decimal | None
    created_at: datetime
    read_at: datetime | None
