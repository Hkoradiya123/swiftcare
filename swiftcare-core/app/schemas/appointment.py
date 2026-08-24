from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.models.enums import AppointmentStatus, AppointmentType


class AppointmentCreate(BaseModel):
    patient_id: int
    provider_id: int
    appointment_type: AppointmentType
    scheduled_start: datetime
    scheduled_end: datetime
    reason: str = Field(min_length=1, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    room_number: Optional[str] = Field(default=None, max_length=20)
    meeting_link: Optional[str] = Field(default=None, max_length=500)

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


class AppointmentComplete(BaseModel):
    summary: str = Field(min_length=1, max_length=5000)
    diagnosis: Optional[str] = Field(default=None, max_length=2000)


class AppointmentFilter(BaseModel):
    patient_id: Optional[int] = None
    provider_id: Optional[int] = None
    status: Optional[AppointmentStatus] = None
    date: Optional[str] = None  # YYYY-MM-DD
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
