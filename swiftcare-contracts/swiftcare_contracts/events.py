from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class AppointmentCompletedEvent(BaseModel):
    event_id: UUID
    event_type: str = "appointment.completed"
    schema_version: int = 1
    appointment_id: int
    patient_id: int
    provider_id: int
    completed_at: datetime
    # denormalized so relay never needs to query core DB
    patient_name: str
    patient_email: str
    provider_name: str
    reason: str
    notes: Optional[str] = None
    summary: Optional[str] = None
    diagnosis: Optional[str] = None


class AppointmentScheduledEvent(BaseModel):
    event_id: UUID
    event_type: str = "appointment.scheduled"
    schema_version: int = 1
    appointment_id: int
    patient_id: int
    provider_id: int
    scheduled_start: datetime
    reason: str
    # denormalized for relay service independence
    patient_name: str
    patient_email: str
    provider_name: str
    provider_email: Optional[str] = None
    provider_briefing: Optional[str] = None


class PrescriptionItemData(BaseModel):
    drug_name: str
    dosage_amount: float
    dosage_unit: str
    frequency_per_day: int
    duration_days: int
    instructions: Optional[str] = None


class PrescriptionCreatedEvent(BaseModel):
    event_id: UUID
    event_type: str = "prescription.created"
    schema_version: int = 1
    prescription_id: int
    appointment_id: int
    patient_id: int
    provider_id: int
    created_at: datetime
    # denormalized so relay never needs to query core DB
    patient_name: str
    patient_email: str
    provider_name: str
    items: list[PrescriptionItemData]


class PasswordResetRequestedEvent(BaseModel):
    event_id: UUID
    event_type: str = "auth.password_reset_requested"
    schema_version: int = 1
    user_email: str
    user_name: str
    reset_token: str  # raw token — notify sends this in email, core stores only hash
