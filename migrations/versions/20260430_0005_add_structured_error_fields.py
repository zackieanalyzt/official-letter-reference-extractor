"""add structured error fields

Revision ID: 20260430_0005
Revises: 20260424_0004
Create Date: 2026-04-30 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260430_0005"
down_revision: str | None = "20260424_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("processing_error_type", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("processing_error_detail", sa.Text(), nullable=True))
    op.add_column("document_references", sa.Column("resolution_error_type", sa.Text(), nullable=True))
    op.add_column("document_references", sa.Column("resolution_error_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_references", "resolution_error_detail")
    op.drop_column("document_references", "resolution_error_type")
    op.drop_column("documents", "processing_error_detail")
    op.drop_column("documents", "processing_error_type")
