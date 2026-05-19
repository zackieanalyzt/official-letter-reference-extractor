"""add reference traversal planning table

Revision ID: 20260519_0012
Revises: 20260510_0011
Create Date: 2026-05-19 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260519_0012"
down_revision: str | None = "20260510_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "reference_traversals",
        sa.Column("id", pk_type, primary_key=True, autoincrement=True),
        sa.Column(
            "parent_document_id",
            pk_type,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_reference_id",
            pk_type,
            sa.ForeignKey("document_references.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_document_id",
            pk_type,
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("raw_url", sa.Text(), nullable=False),
        sa.Column("resolved_url", sa.Text(), nullable=True),
        sa.Column("traversal_depth", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("traversal_status", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("content_length_bytes", pk_type, nullable=True),
        sa.Column("policy_decision", sa.String(length=50), nullable=False),
        sa.Column("policy_reason", sa.Text(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "parent_document_id",
            "source_reference_id",
            "raw_url",
            name="uq_reference_traversals_parent_source_raw_url",
        ),
    )
    op.create_index(
        "ix_reference_traversals_parent_depth",
        "reference_traversals",
        ["parent_document_id", "traversal_depth"],
        unique=False,
    )
    op.create_index(
        "ix_reference_traversals_source_reference_id",
        "reference_traversals",
        ["source_reference_id"],
        unique=False,
    )
    op.create_index(
        "ix_reference_traversals_child_document_id",
        "reference_traversals",
        ["child_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_reference_traversals_status",
        "reference_traversals",
        ["traversal_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reference_traversals_status", table_name="reference_traversals")
    op.drop_index("ix_reference_traversals_child_document_id", table_name="reference_traversals")
    op.drop_index("ix_reference_traversals_source_reference_id", table_name="reference_traversals")
    op.drop_index("ix_reference_traversals_parent_depth", table_name="reference_traversals")
    op.drop_table("reference_traversals")
