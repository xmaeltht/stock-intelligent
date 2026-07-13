import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    exchange: Mapped[str | None] = mapped_column(String(32), index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default="Stock", index=True)
    cik: Mapped[str | None] = mapped_column(String(10), index=True)
    sector: Mapped[str | None] = mapped_column(String(128), index=True)
    industry: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str] = mapped_column(String(2), default="US")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_research_eligible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    eligibility_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    analysis_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    analysis_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
