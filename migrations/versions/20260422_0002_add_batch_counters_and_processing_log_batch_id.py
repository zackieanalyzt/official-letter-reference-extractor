"""add batch counters and processing log batch id

Revision ID: 20260422_0002
Revises: 20260422_0001
Create Date: 2026-04-22 14:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260422_0002"
down_revision: str | None = "20260422_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "batch_runs",
        sa.Column("duplicate_files_skipped", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "batch_runs",
        sa.Column("failed_files", sa.Integer(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("processing_logs") as batch_op:
        batch_op.add_column(sa.Column("batch_run_id", PK_TYPE, nullable=True))
        batch_op.create_foreign_key(
            "fk_processing_logs_batch_run_id_batch_runs",
            "batch_runs",
            ["batch_run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("processing_logs") as batch_op:
        batch_op.drop_constraint("fk_processing_logs_batch_run_id_batch_runs", type_="foreignkey")
        batch_op.drop_column("batch_run_id")
    op.drop_column("batch_runs", "failed_files")
    op.drop_column("batch_runs", "duplicate_files_skipped")
