"""add document reference uniqueness

Revision ID: 20260423_0003
Revises: 20260422_0002
Create Date: 2026-04-23 10:00:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260423_0003"
down_revision: str | None = "20260422_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_document_references_document_page_raw_source",
        "document_references",
        ["document_id", "page_number", "raw_reference", "source_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_document_references_document_page_raw_source",
        "document_references",
        type_="unique",
    )
