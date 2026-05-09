"""add storage hardening metadata

Revision ID: 20260509_0010
Revises: 20260508_0009
Create Date: 2026-05-09 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_0010"
down_revision: str | None = "20260508_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("storage_backend", sa.String(length=50), nullable=False, server_default="localfs"),
    )
    op.add_column("documents", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column(
        "documents",
        sa.Column("lifecycle_state", sa.String(length=50), nullable=False, server_default="uploaded"),
    )
    op.create_index("ix_documents_lifecycle_state", "documents", ["lifecycle_state"], unique=False)

    op.execute("UPDATE documents SET sha256 = content_hash WHERE sha256 IS NULL")
    op.execute(
        """
        UPDATE documents
        SET lifecycle_state = CASE
            WHEN processing_status = 'processed' THEN 'processed'
            WHEN processing_status = 'failed' AND source_file_present = 1 THEN 'retained'
            WHEN processing_status = 'failed' THEN 'failed'
            ELSE 'uploaded'
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_documents_lifecycle_state", table_name="documents")
    op.drop_column("documents", "lifecycle_state")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "storage_backend")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "sha256")
