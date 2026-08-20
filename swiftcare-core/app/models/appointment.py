from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import AppointmentStatus
from app.utils.time import utcnow


class DomainError(ValueError):
    pass


# --- Pure state-machine functions (testable without ORM) ---

def transition_check_in_in_person(status: str) -> str:
    if status != AppointmentStatus.SCHEDULED.value:
        raise DomainError("Can only check in scheduled appointments")
    return AppointmentStatus.CHECKED_IN.value


def transition_check_in_telehealth(status: str) -> str:
    if status != AppointmentStatus.SCHEDULED.value:
        raise DomainError("Can only start scheduled appointments")
    return AppointmentStatus.IN_PROGRESS.value


def transition_complete(status: str) -> str:
    if status not in (AppointmentStatus.CHECKED_IN.value, AppointmentStatus.IN_PROGRESS.value):
        raise DomainError("Can only complete checked-in or in-progress appointments")
    return AppointmentStatus.COMPLETED.value


def transition_cancel(status: str) -> str:
    if status not in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CHECKED_IN.value):
        raise DomainError("Can only cancel scheduled or checked-in appointments")
    return AppointmentStatus.CANCELLED.value


class Appointment(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)
    appointment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AppointmentStatus.SCHEDULED.value, nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    room_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    meeting_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", lazy="raise")
    provider: Mapped["Provider"] = relationship("Provider", lazy="raise")

    __mapper_args__ = {
        "polymorphic_on": "appointment_type",
        "polymorphic_identity": "base",
    }

    def check_in(self) -> None:
        raise NotImplementedError

    def complete(self) -> None:
        self.status = transition_complete(self.status)
        self.completed_at = utcnow()

    def cancel(self) -> None:
        self.status = transition_cancel(self.status)


class InPersonAppointment(Appointment):
    __mapper_args__ = {"polymorphic_identity": "in_person"}

    def check_in(self) -> None:
        self.status = transition_check_in_in_person(self.status)
        self.checked_in_at = utcnow()


class TelehealthAppointment(Appointment):
    __mapper_args__ = {"polymorphic_identity": "telehealth"}

    def check_in(self) -> None:
        self.status = transition_check_in_telehealth(self.status)
        self.checked_in_at = utcnow()
