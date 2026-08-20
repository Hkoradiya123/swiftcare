"""add_prescriptions_and_allergies

Revision ID: c1a2b3d4e5f6
Revises: 3287126715a9
Create Date: 2026-08-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3287126715a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prescriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
    )
    op.create_index("ix_prescriptions_appointment_id", "prescriptions", ["appointment_id"])
    op.create_index("ix_prescriptions_provider_id", "prescriptions", ["provider_id"])
    op.create_index("ix_prescriptions_patient_id", "prescriptions", ["patient_id"])
    op.create_index("ix_prescriptions_deleted_at", "prescriptions", ["deleted_at"])

    op.create_table(
        "prescription_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prescription_id", sa.Integer(), nullable=False),
        sa.Column("drug_name", sa.String(200), nullable=False),
        sa.Column("dosage_amount", sa.Numeric(8, 3), nullable=False),
        sa.Column("dosage_unit", sa.String(20), nullable=False),
        sa.Column("frequency_per_day", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_prescription_items_prescription_id", "prescription_items", ["prescription_id"])

    op.create_table(
        "allergies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("allergen", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("reaction", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_allergies_patient_id", "allergies", ["patient_id"])
    op.create_index("ix_allergies_deleted_at", "allergies", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("allergies")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
