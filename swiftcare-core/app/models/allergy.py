from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, String, Text, event, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import AllergyType, AllergySeverity


class Allergy(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "allergies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    allergen: Mapped[str] = mapped_column(String(100), nullable=False)
    allergen_normalized: Mapped[str] = mapped_column(String(100), nullable=False)

    allergy_type: Mapped[AllergyType] = mapped_column(
        Enum(AllergyType, name="allergy_type", native_enum=True),
        nullable=False,
    )
    severity: Mapped[AllergySeverity] = mapped_column(
        Enum(AllergySeverity, name="allergy_severity", native_enum=True),
        nullable=False,
    )
    reaction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )

    patient: Mapped["Patient"] = relationship(back_populates="allergies")

    __table_args__ = (
        # Only active (non-deleted) rows are unique per patient+allergen
        Index(
            "uq_active_patient_allergen",
            "patient_id", "allergen_normalized",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Filtered index for fast drug-allergy lookup during prescription checks
        Index(
            "ix_allergy_drug_lookup",
            "patient_id", "allergen_normalized",
            postgresql_where=text("deleted_at IS NULL AND allergy_type = 'drug'"),
        ),
    )


@event.listens_for(Allergy, "before_insert")
@event.listens_for(Allergy, "before_update")
def _normalize_allergen(mapper, connection, target: Allergy) -> None:
    target.allergen_normalized = target.allergen.strip().lower()
