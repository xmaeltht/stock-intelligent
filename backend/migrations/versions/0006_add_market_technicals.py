"""Add volume, chart history, and deterministic technical indicators.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stock_analyses", sa.Column("volume", sa.BigInteger(), nullable=True))
    op.add_column(
        "stock_analyses",
        sa.Column("price_history", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "stock_analyses",
        sa.Column("technical_indicators", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_stock_analyses_volume", "stock_analyses", ["volume"])


def downgrade() -> None:
    op.drop_index("ix_stock_analyses_volume", table_name="stock_analyses")
    op.drop_column("stock_analyses", "technical_indicators")
    op.drop_column("stock_analyses", "price_history")
    op.drop_column("stock_analyses", "volume")
