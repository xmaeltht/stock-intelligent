"""Remove stale corporate ETF ratings and queue fund screening.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM stock_analyses
        USING companies
        WHERE stock_analyses.company_id = companies.id
          AND companies.asset_type = 'ETF'
        """
    )
    op.execute(
        """
        UPDATE companies
        SET analysis_attempted_at = NULL,
            analysis_error = NULL
        WHERE asset_type = 'ETF'
        """
    )


def downgrade() -> None:
    pass
