"""add retention metadata and document ingestions

Revision ID: 20260507_0008
Revises: 20260503_0007
Create Date: 2026-05-07 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260507_0008"
down_revision: str | None = "20260503_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    op.add_column("documents", sa.Column("extraction_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "documents",
        sa.Column("retention_mode", sa.String(length=50), nullable=False, server_default="retain_failed_only"),
    )
    op.add_column("documents", sa.Column("source_file_present", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("source_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("last_source_path", sa.Text(), nullable=True))
    op.add_column(
        "documents", sa.Column("retry_requires_reupload", sa.Boolean(), nullable=False, server_default="0")
    )
    op.add_column(
        "documents",
        sa.Column("last_ingestion_used_cached_result", sa.Boolean(), nullable=False, server_default="0"),
    )

    op.create_table(
        "document_ingestions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "batch_run_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("batch_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("uploaded_file_name", sa.Text(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ingestion_status", sa.String(length=50), nullable=False),
        sa.Column("used_cached_result", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("force_reprocess_requested", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("retention_mode_used", sa.String(length=50), nullable=False),
        sa.Column("source_file_path", sa.Text(), nullable=True),
        sa.Column("source_file_present", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("source_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_source_available", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )

    _drop_index_if_exists("ix_documents_content_hash", "documents")
    _create_index_if_missing("ix_documents_content_hash", "documents", ["content_hash"], unique=True)
    _create_index_if_missing("ix_documents_source_file_present", "documents", ["source_file_present"])
    _create_index_if_missing("ix_documents_retry_requires_reupload", "documents", ["retry_requires_reupload"])

    _create_index_if_missing("ix_document_ingestions_document_id", "document_ingestions", ["document_id"])
    _create_index_if_missing("ix_document_ingestions_batch_run_id", "document_ingestions", ["batch_run_id"])
    _create_index_if_missing("ix_document_ingestions_uploaded_at", "document_ingestions", ["uploaded_at"])
    _create_index_if_missing(
        "ix_document_ingestions_ingestion_status", "document_ingestions", ["ingestion_status"]
    )
    _create_index_if_missing(
        "ix_document_ingestions_used_cached_result", "document_ingestions", ["used_cached_result"]
    )
    _create_index_if_missing("ix_document_ingestions_cleanup_due_at", "document_ingestions", ["cleanup_due_at"])
    _create_index_if_missing(
        "ix_document_ingestions_source_file_present", "document_ingestions", ["source_file_present"]
    )
    _create_index_if_missing(
        "ix_document_ingestions_retry_source_available", "document_ingestions", ["retry_source_available"]
    )


def downgrade() -> None:
    _drop_index_if_exists("ix_document_ingestions_retry_source_available", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_source_file_present", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_cleanup_due_at", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_used_cached_result", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_ingestion_status", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_uploaded_at", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_batch_run_id", "document_ingestions")
    _drop_index_if_exists("ix_document_ingestions_document_id", "document_ingestions")
    _drop_index_if_exists("ix_documents_retry_requires_reupload", "documents")
    _drop_index_if_exists("ix_documents_source_file_present", "documents")
    _drop_index_if_exists("ix_documents_content_hash", "documents")
    _create_index_if_missing("ix_documents_content_hash", "documents", ["content_hash"])
    op.drop_table("document_ingestions")
    op.drop_column("documents", "last_ingestion_used_cached_result")
    op.drop_column("documents", "retry_requires_reupload")
    op.drop_column("documents", "last_source_path")
    op.drop_column("documents", "source_deleted_at")
    op.drop_column("documents", "source_file_present")
    op.drop_column("documents", "retention_mode")
    op.drop_column("documents", "extraction_version")
