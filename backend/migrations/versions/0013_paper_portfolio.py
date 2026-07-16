"""Add the paper portfolio and append-only trade journal.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-16
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_portfolios",
        sa.Column("id", sa.Uuid(), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("starting_cash", sa.Numeric(20, 2), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 2), nullable=False),
        sa.Column("max_risk_per_trade_pct", sa.Float(), nullable=False),
        sa.Column("max_position_pct", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Uuid(), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "portfolio_id",
            sa.Uuid(),
            sa.ForeignKey("paper_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("price", sa.Numeric(20, 4), nullable=False),
        sa.Column("fees", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(20, 2), nullable=True),
        sa.Column("thesis", sa.String(2000), nullable=True),
        sa.Column("catalyst", sa.String(1000), nullable=True),
        sa.Column("invalidation_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("target_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column(
            "executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_paper_trades_portfolio_id", "paper_trades", ["portfolio_id"])
    op.create_index("ix_paper_trades_company_id", "paper_trades", ["company_id"])
    op.create_index("ix_paper_trades_side", "paper_trades", ["side"])
    op.create_index("ix_paper_trades_executed_at", "paper_trades", ["executed_at"])


def downgrade() -> None:
    op.drop_table("paper_trades")
    op.drop_table("paper_portfolios")
