"""Classify likely derivative securities out of the research universe.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("is_research_eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "companies", sa.Column("eligibility_reason", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_companies_is_research_eligible", "companies", ["is_research_eligible"]
    )
    op.execute(
        """
        UPDATE companies AS derivative
        SET is_research_eligible = FALSE,
            eligibility_reason = 'Likely warrant, unit, or right with common-share sibling'
        WHERE
            (
                RIGHT(derivative.ticker, 2) = 'WS'
                AND EXISTS (
                    SELECT 1 FROM companies AS common
                    WHERE common.cik = derivative.cik
                      AND common.ticker = LEFT(derivative.ticker, LENGTH(derivative.ticker) - 2)
                )
            )
            OR (
                RIGHT(derivative.ticker, 1) IN ('W', 'U', 'R')
                AND EXISTS (
                    SELECT 1 FROM companies AS common
                    WHERE common.cik = derivative.cik
                      AND common.ticker = LEFT(derivative.ticker, LENGTH(derivative.ticker) - 1)
                )
            )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_companies_is_research_eligible", table_name="companies")
    op.drop_column("companies", "eligibility_reason")
    op.drop_column("companies", "is_research_eligible")
