from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    event_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str


class AppointmentCreatedEvent(BaseEvent):
    event_type: str = "appointment.created"
    appointment_id: int
    patient_id: int
    provider_id: int
    patient_email: str
    patient_name: str
    provider_name: str
    scheduled_start: datetime
    scheduled_end: datetime
    appointment_type: str


class PrescriptionIssuedEvent(BaseEvent):
    event_type: str = "prescription.issued"
    prescription_id: int
    appointment_id: int
    patient_id: int
    provider_id: int
    patient_email: str
    patient_name: str
    is_controlled_substance: bool = False
    medications: list[Dict[str, Any]]


class ReminderTriggeredEvent(BaseEvent):
    event_type: str = "reminder.triggered"
    appointment_id: int
    patient_id: int
    patient_email: str
    patient_name: str
    scheduled_start: datetime
    reminder_type: str  # "24h" or "2h"
