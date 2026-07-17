"""Make the watchlist per-user.

Adds a user_id column, drops the global unique-on-company index, and enforces
uniqueness per (user, company) instead. Existing rows keep a NULL user_id and
are simply no longer surfaced (a clean pivot to accounts).

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "watchlist_entries",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    # Replace the global unique-on-company index with per-user scoping.
    op.drop_index("ix_watchlist_entries_company_id", table_name="watchlist_entries")
    op.create_index("ix_watchlist_entries_company_id", "watchlist_entries", ["company_id"])
    op.create_index("ix_watchlist_entries_user_id", "watchlist_entries", ["user_id"])
    op.create_unique_constraint(
        "uq_watchlist_user_company", "watchlist_entries", ["user_id", "company_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_watchlist_user_company", "watchlist_entries", type_="unique")
    op.drop_index("ix_watchlist_entries_user_id", table_name="watchlist_entries")
    op.drop_index("ix_watchlist_entries_company_id", table_name="watchlist_entries")
    op.create_index(
        "ix_watchlist_entries_company_id",
        "watchlist_entries",
        ["company_id"],
        unique=True,
    )
    op.drop_column("watchlist_entries", "user_id")
