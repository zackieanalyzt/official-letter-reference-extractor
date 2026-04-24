"""add document reference filter indexes

Revision ID: 20260424_0004
Revises: 20260423_0003
Create Date: 2026-04-24 13:10:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260424_0004"
down_revision: str | None = "20260423_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_document_references_resolution_status",
        "document_references",
        ["resolution_status"],
        unique=False,
    )
    op.create_index(
        "ix_document_references_source_type",
        "document_references",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_references_source_type", table_name="document_references")
    op.drop_index("ix_document_references_resolution_status", table_name="document_references")
