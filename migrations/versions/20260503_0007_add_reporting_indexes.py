"""add reporting indexes

Revision ID: 20260503_0007
Revises: 20260503_0006
Create Date: 2026-05-03 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260503_0007"
down_revision: str | None = "20260503_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    _create_index_if_missing("ix_documents_processing_status", "documents", ["processing_status"])
    _create_index_if_missing("ix_documents_processing_error_type", "documents", ["processing_error_type"])
    _create_index_if_missing("ix_documents_processed_at", "documents", ["processed_at"])
    _create_index_if_missing(
        "ix_document_references_resolution_error_type",
        "document_references",
        ["resolution_error_type"],
    )
    _create_index_if_missing("ix_document_references_final_url", "document_references", ["final_url"])


def downgrade() -> None:
    _drop_index_if_exists("ix_document_references_final_url", "document_references")
    _drop_index_if_exists("ix_document_references_resolution_error_type", "document_references")
    _drop_index_if_exists("ix_documents_processed_at", "documents")
    _drop_index_if_exists("ix_documents_processing_error_type", "documents")
    _drop_index_if_exists("ix_documents_processing_status", "documents")
