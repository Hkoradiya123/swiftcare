from datetime import datetime
from typing import Optional
from pydantic import BaseModel, model_validator

from app.models.enums import AppointmentStatus, AppointmentType


class AppointmentCreate(BaseModel):
    patient_id: int
    provider_id: int
    appointment_type: AppointmentType
    scheduled_start: datetime
    scheduled_end: datetime
    reason: str
    notes: Optional[str] = None
    room_number: Optional[str] = None
    meeting_link: Optional[str] = None

    @model_validator(mode="after")
    def end_after_start(self):
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        return self


class AppointmentRead(BaseModel):
    id: int
    patient_id: int
    provider_id: int
    appointment_type: str
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    checked_in_at: Optional[datetime]
    completed_at: Optional[datetime]
    reason: str
    notes: Optional[str]
    room_number: Optional[str]
    meeting_link: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentFilter(BaseModel):
    provider_id: Optional[int] = None
    status: Optional[AppointmentStatus] = None
    date: Optional[str] = None  # YYYY-MM-DD
    page: int = 1
    page_size: int = 20
