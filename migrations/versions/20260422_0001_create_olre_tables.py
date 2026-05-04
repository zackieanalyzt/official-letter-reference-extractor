"""create olre tables

Revision ID: 20260422_0001
Revises:
Create Date: 2026-04-22 11:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260422_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "batch_runs",
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("triggered_by", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("total_files_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_files_processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_references_found", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "documents",
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("batch_run_id", PK_TYPE, nullable=True),
        sa.Column("original_file_name", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", PK_TYPE, nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("document_number", sa.String(length=255), nullable=True),
        sa.Column("processing_status", sa.String(length=50), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moved_to_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["batch_run_id"], ["batch_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], unique=False)
    op.create_index("ix_documents_document_number", "documents", ["document_number"], unique=False)

    op.create_table(
        "document_references",
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("document_id", PK_TYPE, nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("reference_class", sa.String(length=50), nullable=False),
        sa.Column("raw_reference", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("resolution_status", sa.String(length=50), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_references_document_id", "document_references", ["document_id"], unique=False
    )

    op.create_table(
        "users_audit",
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("action_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "processing_logs",
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("document_id", PK_TYPE, nullable=True),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_logs_document_id", "processing_logs", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_processing_logs_document_id", table_name="processing_logs")
    op.drop_table("processing_logs")
    op.drop_table("users_audit")
    op.drop_index("ix_document_references_document_id", table_name="document_references")
    op.drop_table("document_references")
    op.drop_index("ix_documents_document_number", table_name="documents")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_table("documents")
    op.drop_table("batch_runs")
