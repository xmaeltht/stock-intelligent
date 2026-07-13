"""Track per-company analysis coverage and failures.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies", sa.Column("analysis_attempted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("companies", sa.Column("analysis_error", sa.String(length=1000), nullable=True))
    op.create_index(
        "ix_companies_analysis_attempted_at", "companies", ["analysis_attempted_at"]
    )
    op.execute(
        """
        UPDATE companies AS c
        SET analysis_attempted_at = latest.as_of
        FROM (
            SELECT company_id, MAX(as_of) AS as_of
            FROM stock_analyses
            GROUP BY company_id
        ) AS latest
        WHERE latest.company_id = c.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_companies_analysis_attempted_at", table_name="companies")
    op.drop_column("companies", "analysis_error")
    op.drop_column("companies", "analysis_attempted_at")
