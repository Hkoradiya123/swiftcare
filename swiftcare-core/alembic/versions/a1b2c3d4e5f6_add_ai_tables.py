"""add visit_summaries and visit_embeddings for AI

Revision ID: a1b2c3d4e5f6
Revises: dbc399b6f17d
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "dbc399b6f17d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "visit_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("document_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index("ix_visit_summaries_patient_id", "visit_summaries", ["patient_id"])

    op.create_table(
        "visit_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_summary_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["visit_summary_id"], ["visit_summaries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visit_embeddings_patient_id", "visit_embeddings", ["patient_id"])
    op.create_index("ix_visit_embeddings_visit_summary_id", "visit_embeddings", ["visit_summary_id"])

    # Add the vector column and HNSW index separately (raw SQL required for pgvector types)
    # Table is always empty here so NOT NULL without a DEFAULT is fine
    op.execute("ALTER TABLE visit_embeddings ADD COLUMN embedding vector(1536) NOT NULL")
    op.execute("CREATE INDEX ix_visit_embeddings_embedding ON visit_embeddings USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("visit_embeddings")
    op.drop_table("visit_summaries")
