"""verify structured error fields

Revision ID: 20260503_0006
Revises: 20260430_0005
Create Date: 2026-05-03 20:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260503_0006"
down_revision: str | None = "20260430_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("documents", sa.Column("processing_error_type", sa.Text(), nullable=True))
    _add_column_if_missing("documents", sa.Column("processing_error_detail", sa.Text(), nullable=True))
    _add_column_if_missing(
        "document_references",
        sa.Column("resolution_error_type", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "document_references",
        sa.Column("resolution_error_detail", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # This migration repairs schema drift. Keep downgrade non-destructive so a
    # downgrade across this verification step does not drop columns created by
    # the canonical 20260430_0005 migration.
    pass
