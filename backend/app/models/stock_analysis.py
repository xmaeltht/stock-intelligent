import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StockAnalysis(Base):
    __tablename__ = "stock_analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price_date: Mapped[date] = mapped_column(Date)
    current_price: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    price_history: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    technical_indicators: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    previous_revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    revenue_growth_pct: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    cash: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    debt: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    eps: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    fair_value: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    bear_value: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    bull_value: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    upside_pct: Mapped[float] = mapped_column(Float, index=True)
    opportunity_score: Mapped[int] = mapped_column(Integer, index=True)
    confidence_grade: Mapped[str] = mapped_column(String(2), index=True)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    qualification: Mapped[str] = mapped_column(String(32), index=True)
    valuation_methods: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    fundamentals: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    catalysts: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    risks: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    thesis_breakers: Mapped[list[str]] = mapped_column(JSON, default=list)
    sources: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company = relationship("Company")
