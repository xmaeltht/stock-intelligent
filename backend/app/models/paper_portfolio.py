import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), default="My paper portfolio")
    starting_cash: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("100000"))
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("100000"))
    max_risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=1.0)
    max_position_pct: Mapped[float] = mapped_column(Float, default=10.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trades = relationship("PaperTrade", back_populates="portfolio", cascade="all, delete-orphan")


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    side: Mapped[str] = mapped_column(String(4), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    thesis: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    catalyst: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    invalidation_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
    )

    portfolio = relationship("PaperPortfolio", back_populates="trades")
    company = relationship("Company")
