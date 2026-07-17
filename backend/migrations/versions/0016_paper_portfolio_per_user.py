"""Make the paper portfolio per-user.

Adds a user_id column (unique — one portfolio per account). The existing
pre-accounts portfolio keeps a NULL user_id and is no longer surfaced.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_portfolios",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_paper_portfolios_user_id", "paper_portfolios", ["user_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_paper_portfolios_user_id", table_name="paper_portfolios")
    op.drop_column("paper_portfolios", "user_id")
