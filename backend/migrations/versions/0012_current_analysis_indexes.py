"""Make current-analysis reads indexed and constant-time per company.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_analyses",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # PostgreSQL is the application database. DISTINCT ON gives each company its
    # newest row in one pass; the UUID tie-breaker makes the result deterministic.
    op.execute(
        """
        UPDATE stock_analyses AS target
        SET is_current = TRUE
        WHERE target.id IN (
            SELECT DISTINCT ON (company_id) id
            FROM stock_analyses
            ORDER BY company_id, as_of DESC, id DESC
        )
        """
    )
    op.create_index(
        "uq_stock_analyses_one_current_company",
        "stock_analyses",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_stock_analyses_current_upside",
        "stock_analyses",
        ["upside_pct"],
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_stock_analyses_current_score",
        "stock_analyses",
        ["opportunity_score"],
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_stock_analyses_current_price",
        "stock_analyses",
        ["current_price"],
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_stock_analyses_current_volume",
        "stock_analyses",
        ["volume"],
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("ix_stock_analyses_current_volume", table_name="stock_analyses")
    op.drop_index("ix_stock_analyses_current_price", table_name="stock_analyses")
    op.drop_index("ix_stock_analyses_current_score", table_name="stock_analyses")
    op.drop_index("ix_stock_analyses_current_upside", table_name="stock_analyses")
    op.drop_index("uq_stock_analyses_one_current_company", table_name="stock_analyses")
    op.drop_column("stock_analyses", "is_current")
