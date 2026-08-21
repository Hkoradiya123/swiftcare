"""add processed_events idempotency table

Revision ID: b2c4e8f1a3d7
Revises: 37373f664fa9
Create Date: 2026-08-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b2c4e8f1a3d7"
down_revision: Union[str, Sequence[str], None] = "37373f664fa9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="relay",
    )


def downgrade() -> None:
    op.drop_table("processed_events", schema="relay")
