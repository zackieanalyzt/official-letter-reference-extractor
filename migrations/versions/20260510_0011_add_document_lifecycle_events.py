"""add document lifecycle events

Revision ID: 20260510_0011
Revises: 20260509_0010
Create Date: 2026-05-10 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260510_0011"
down_revision: str | None = "20260509_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_lifecycle_events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("from_state", sa.String(length=50), nullable=True),
        sa.Column("to_state", sa.String(length=50), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_source", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("operation_id", sa.String(length=100), nullable=True),
        sa.Column(
            "batch_run_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("batch_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_lifecycle_events_document_occurred",
        "document_lifecycle_events",
        ["document_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_document_lifecycle_events_event_occurred",
        "document_lifecycle_events",
        ["event_type", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_document_lifecycle_events_batch_run_id",
        "document_lifecycle_events",
        ["batch_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_lifecycle_events_correlation_id",
        "document_lifecycle_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_lifecycle_events_to_state",
        "document_lifecycle_events",
        ["to_state"],
        unique=False,
    )

    op.execute(
        """
        UPDATE documents
        SET lifecycle_state = CASE
            WHEN lifecycle_state = 'processed' THEN 'resolved'
            WHEN lifecycle_state = 'deleted' THEN 'cleaned'
            ELSE lifecycle_state
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_lifecycle_events_to_state", table_name="document_lifecycle_events")
    op.drop_index("ix_document_lifecycle_events_correlation_id", table_name="document_lifecycle_events")
    op.drop_index("ix_document_lifecycle_events_batch_run_id", table_name="document_lifecycle_events")
    op.drop_index("ix_document_lifecycle_events_event_occurred", table_name="document_lifecycle_events")
    op.drop_index("ix_document_lifecycle_events_document_occurred", table_name="document_lifecycle_events")
    op.drop_table("document_lifecycle_events")
