"""add traversal review state and audit history

Revision ID: 20260522_0010
Revises: 20260508_0009
Create Date: 2026-05-22 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260522_0010"
down_revision: str | None = "20260508_0009"
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
    op.add_column("document_references", sa.Column("confidence_score", sa.Integer(), nullable=True))
    op.add_column(
        "document_references",
        sa.Column("risk_level", sa.String(length=50), nullable=False, server_default="MEDIUM"),
    )
    op.add_column(
        "document_references",
        sa.Column("recommended_action", sa.String(length=50), nullable=False, server_default="REVIEW_REQUIRED"),
    )
    op.add_column(
        "document_references",
        sa.Column("review_status", sa.String(length=50), nullable=False, server_default="PENDING_REVIEW"),
    )
    op.add_column("document_references", sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column("document_references", sa.Column("evidence_summary", sa.Text(), nullable=True))
    op.add_column("document_references", sa.Column("operator_decision", sa.String(length=50), nullable=True))
    op.add_column("document_references", sa.Column("operator_note", sa.Text(), nullable=True))
    op.add_column("document_references", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "reference_traversal_reviews",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column(
            "traversal_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("document_references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("review_status", sa.String(length=50), nullable=False),
        sa.Column("operator_decision", sa.String(length=50), nullable=True),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("acted_by", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_detail", sa.Text(), nullable=True),
    )

    _create_index_if_missing(
        "ix_document_references_recommended_action", "document_references", ["recommended_action"]
    )
    _create_index_if_missing("ix_document_references_review_status", "document_references", ["review_status"])
    _create_index_if_missing("ix_document_references_risk_level", "document_references", ["risk_level"])
    _create_index_if_missing(
        "ix_document_references_recommended_action_review_status",
        "document_references",
        ["recommended_action", "review_status"],
    )
    _create_index_if_missing(
        "ix_reference_traversal_reviews_traversal_id", "reference_traversal_reviews", ["traversal_id"]
    )
    _create_index_if_missing(
        "ix_reference_traversal_reviews_review_status", "reference_traversal_reviews", ["review_status"]
    )
    _create_index_if_missing(
        "ix_reference_traversal_reviews_created_at", "reference_traversal_reviews", ["created_at"]
    )
    _create_index_if_missing(
        "ix_reference_traversal_reviews_event_type", "reference_traversal_reviews", ["event_type"]
    )


def downgrade() -> None:
    _drop_index_if_exists("ix_reference_traversal_reviews_event_type", "reference_traversal_reviews")
    _drop_index_if_exists("ix_reference_traversal_reviews_created_at", "reference_traversal_reviews")
    _drop_index_if_exists("ix_reference_traversal_reviews_review_status", "reference_traversal_reviews")
    _drop_index_if_exists("ix_reference_traversal_reviews_traversal_id", "reference_traversal_reviews")
    _drop_index_if_exists(
        "ix_document_references_recommended_action_review_status",
        "document_references",
    )
    _drop_index_if_exists("ix_document_references_risk_level", "document_references")
    _drop_index_if_exists("ix_document_references_review_status", "document_references")
    _drop_index_if_exists("ix_document_references_recommended_action", "document_references")
    op.drop_table("reference_traversal_reviews")
    op.drop_column("document_references", "reviewed_at")
    op.drop_column("document_references", "operator_note")
    op.drop_column("document_references", "operator_decision")
    op.drop_column("document_references", "evidence_summary")
    op.drop_column("document_references", "review_reason")
    op.drop_column("document_references", "review_status")
    op.drop_column("document_references", "recommended_action")
    op.drop_column("document_references", "risk_level")
    op.drop_column("document_references", "confidence_score")
