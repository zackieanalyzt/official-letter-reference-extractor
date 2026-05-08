"""add destination classification fields to document references

Revision ID: 20260508_0009
Revises: 20260507_0008
Create Date: 2026-05-08 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260508_0009"
down_revision: str | None = "20260507_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_references", sa.Column("destination_type", sa.String(length=50), nullable=True))
    op.add_column("document_references", sa.Column("destination_host", sa.String(length=255), nullable=True))
    op.add_column("document_references", sa.Column("requires_user_action", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_references", "requires_user_action")
    op.drop_column("document_references", "destination_host")
    op.drop_column("document_references", "destination_type")
