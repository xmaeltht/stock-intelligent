"""Create stock analyses table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("current_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("revenue", sa.Numeric(24, 2), nullable=True),
        sa.Column("previous_revenue", sa.Numeric(24, 2), nullable=True),
        sa.Column("revenue_growth_pct", sa.Float(), nullable=True),
        sa.Column("net_income", sa.Numeric(24, 2), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(24, 2), nullable=True),
        sa.Column("cash", sa.Numeric(24, 2), nullable=True),
        sa.Column("debt", sa.Numeric(24, 2), nullable=True),
        sa.Column("shares_outstanding", sa.Numeric(24, 2), nullable=True),
        sa.Column("eps", sa.Numeric(20, 4), nullable=True),
        sa.Column("fair_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("bear_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("bull_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("upside_pct", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Integer(), nullable=False),
        sa.Column("confidence_grade", sa.String(2), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("qualification", sa.String(32), nullable=False),
        sa.Column("valuation_methods", sa.JSON(), nullable=False),
        sa.Column("catalysts", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("thesis_breakers", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "company_id",
        "as_of",
        "upside_pct",
        "opportunity_score",
        "confidence_grade",
        "risk_level",
        "qualification",
    ):
        op.create_index(f"ix_stock_analyses_{column}", "stock_analyses", [column])


def downgrade() -> None:
    op.drop_table("stock_analyses")
