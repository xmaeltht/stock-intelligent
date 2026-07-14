"""Track the last intraday price refresh for the live-quote loop.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_analyses",
        sa.Column("price_as_of", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_stock_analyses_price_as_of", "stock_analyses", ["price_as_of"]
    )


def downgrade() -> None:
    op.drop_index("ix_stock_analyses_price_as_of", table_name="stock_analyses")
    op.drop_column("stock_analyses", "price_as_of")
