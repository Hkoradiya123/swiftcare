"""add_document_records

Revision ID: c3d5f9b2e4a1
Revises: b2c4e8f1a3d7
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d5f9b2e4a1'
down_revision: Union[str, Sequence[str], None] = 'b2c4e8f1a3d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=False),
        sa.Column('s3_bucket', sa.String(length=255), nullable=False),
        sa.Column('s3_key', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='relay',
    )
    op.create_index(
        op.f('ix_relay_document_records_appointment_id'),
        'document_records', ['appointment_id'], unique=False, schema='relay',
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_relay_document_records_appointment_id'),
        table_name='document_records', schema='relay',
    )
    op.drop_table('document_records', schema='relay')
