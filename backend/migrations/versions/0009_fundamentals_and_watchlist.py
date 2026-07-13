"""Store multi-year fundamentals and add the research watchlist.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-13
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_analyses",
        sa.Column("fundamentals", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "watchlist_entries",
        sa.Column("id", sa.Uuid(), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "company_id",
            sa.Uuid(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_watchlist_entries_company_id",
        "watchlist_entries",
        ["company_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_watchlist_entries_company_id", table_name="watchlist_entries")
    op.drop_table("watchlist_entries")
    op.drop_column("stock_analyses", "fundamentals")
