"""Allow multiple securities for one SEC registrant.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_companies_cik", table_name="companies")
    op.create_index("ix_companies_cik", "companies", ["cik"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_companies_cik", table_name="companies")
    op.create_index("ix_companies_cik", "companies", ["cik"], unique=True)
