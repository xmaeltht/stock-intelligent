"""Classify stocks and ETFs.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("asset_type", sa.String(length=16), nullable=False, server_default="Stock"),
    )
    op.create_index("ix_companies_asset_type", "companies", ["asset_type"])
    op.execute("UPDATE companies SET asset_type = 'ETF' WHERE name ILIKE '% ETF%'")


def downgrade() -> None:
    op.drop_index("ix_companies_asset_type", table_name="companies")
    op.drop_column("companies", "asset_type")
