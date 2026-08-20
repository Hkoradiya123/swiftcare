"""harden_allergy_model

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-08-20 19:00:00.000000

Changes:
- Drop old allergies table (String severity, no type, no normalization)
- Create Postgres enum types: allergy_severity, allergy_type
- Recreate allergies table with: allergen_normalized, allergy_type enum,
  severity enum, recorded_by_id, ondelete CASCADE, partial unique index,
  filtered drug-lookup index
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("allergies")

    # Create enum types idempotently (first run may have partially committed them)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'allergy_severity') THEN
                CREATE TYPE allergy_severity AS ENUM ('mild','moderate','severe','life_threatening');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'allergy_type') THEN
                CREATE TYPE allergy_type AS ENUM ('drug','food','environmental');
            END IF;
        END $$;
    """)

    # Use raw SQL to avoid SQLAlchemy re-creating enum types during create_table
    op.execute("""
        CREATE TABLE allergies (
            id              SERIAL PRIMARY KEY,
            patient_id      INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            allergen        VARCHAR(100) NOT NULL,
            allergen_normalized VARCHAR(100) NOT NULL,
            allergy_type    allergy_type NOT NULL,
            severity        allergy_severity NOT NULL,
            reaction        TEXT,
            recorded_by_id  INTEGER REFERENCES providers(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL,
            updated_at      TIMESTAMPTZ NOT NULL,
            deleted_at      TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_active_patient_allergen
        ON allergies (patient_id, allergen_normalized)
        WHERE deleted_at IS NULL
    """)
    op.execute("""
        CREATE INDEX ix_allergy_drug_lookup
        ON allergies (patient_id, allergen_normalized)
        WHERE deleted_at IS NULL AND allergy_type = 'drug'
    """)


def downgrade() -> None:
    op.drop_table("allergies")
    op.execute("DROP TYPE IF EXISTS allergy_severity")
    op.execute("DROP TYPE IF EXISTS allergy_type")

    op.execute("""
        CREATE TABLE allergies (
            id         SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL REFERENCES patients(id),
            allergen   VARCHAR(100) NOT NULL,
            severity   VARCHAR(20) NOT NULL,
            reaction   VARCHAR(300),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            deleted_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX ix_allergies_patient_id ON allergies (patient_id)")
    op.execute("CREATE INDEX ix_allergies_deleted_at ON allergies (deleted_at)")
