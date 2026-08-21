from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Boolean, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import RelayBase


def _now() -> datetime:
    from datetime import timezone
    return datetime.now(timezone.utc)


class ProcessedEvent(RelayBase):
    """Idempotency table — prevents duplicate processing on XACK-before-crash retry."""
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentRecord(RelayBase):
    __tablename__ = "document_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AppointmentSlot(RelayBase):
    """Local cache of scheduled appointments — populated by appointment.scheduled events."""
    __tablename__ = "appointment_slots"

    appointment_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # core's ID, not autoincrement
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    patient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ReminderLog(RelayBase):
    __tablename__ = "reminder_logs"
    # (appointment_id, reminder_type) unique — prevents duplicate reminders on retry/restart
    __table_args__ = (
        UniqueConstraint("appointment_id", "reminder_type", name="uq_appt_reminder_type"),
        {"schema": "relay"},  # must repeat — overriding RelayBase.__table_args__
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    patient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    reminder_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "24h_before" or "2h_before"
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class TaskLog(RelayBase):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending, success, failed
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
