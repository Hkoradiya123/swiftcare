from decimal import Decimal
from typing import Optional
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import PrescriptionStatus


class Prescription(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), index=True, nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=PrescriptionStatus.ACTIVE.value, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    items: Mapped[list["PrescriptionItem"]] = relationship("PrescriptionItem", back_populates="prescription", lazy="raise")


class PrescriptionItem(Base, TimestampMixin):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True, nullable=False)
    drug_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage_amount: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    dosage_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    frequency_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    prescription: Mapped["Prescription"] = relationship("Prescription", back_populates="items", lazy="raise")


