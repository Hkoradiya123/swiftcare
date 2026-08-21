"""add_appointment_slots_and_reminder_unique_constraint

Revision ID: d4e6a8c1f3b2
Revises: c3d5f9b2e4a1
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e6a8c1f3b2'
down_revision: Union[str, Sequence[str], None] = 'c3d5f9b2e4a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'appointment_slots',
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('patient_name', sa.String(length=255), nullable=False),
        sa.Column('patient_email', sa.String(length=255), nullable=False),
        sa.Column('provider_name', sa.String(length=255), nullable=False),
        sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('appointment_id'),
        schema='relay',
    )
    op.create_index(
        op.f('ix_relay_appointment_slots_scheduled_start'),
        'appointment_slots', ['scheduled_start'], unique=False, schema='relay',
    )
    op.create_index(
        op.f('ix_relay_appointment_slots_patient_email'),
        'appointment_slots', ['patient_email'], unique=False, schema='relay',
    )
    op.create_unique_constraint(
        'uq_appt_reminder_type',
        'reminder_logs',
        ['appointment_id', 'reminder_type'],
        schema='relay',
    )


def downgrade() -> None:
    op.drop_constraint('uq_appt_reminder_type', 'reminder_logs', schema='relay', type_='unique')
    op.drop_index(
        op.f('ix_relay_appointment_slots_patient_email'),
        table_name='appointment_slots', schema='relay',
    )
    op.drop_index(
        op.f('ix_relay_appointment_slots_scheduled_start'),
        table_name='appointment_slots', schema='relay',
    )
    op.drop_table('appointment_slots', schema='relay')
