from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator


class ProviderCreate(BaseModel):
    specialization: str
    license_number: str
    consultation_fee: Decimal
    default_slot_minutes: int = 30

    @field_validator("consultation_fee")
    @classmethod
    def fee_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Fee must be positive")
        return v

    @field_validator("default_slot_minutes")
    @classmethod
    def slot_valid(cls, v: int) -> int:
        if v not in (15, 20, 30, 45, 60):
            raise ValueError("Slot must be 15/20/30/45/60 minutes")
        return v


class ProviderUpdate(BaseModel):
    specialization: Optional[str] = None
    consultation_fee: Optional[Decimal] = None
    default_slot_minutes: Optional[int] = None


class ProviderRead(BaseModel):
    id: int
    user_id: int
    specialization: str
    license_number: str
    consultation_fee: Decimal
    default_slot_minutes: int
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class ProviderAvailabilityCreate(BaseModel):
    weekday: int        # 0=Mon, 6=Sun
    start_time: str     # "09:00"
    end_time: str       # "17:00"

    @field_validator("weekday")
    @classmethod
    def weekday_valid(cls, v: int) -> int:
        if v not in range(7):
            raise ValueError("Weekday must be between 0 and 6")
        return v


class ProviderAvailabilityRead(BaseModel):
    id: int
    weekday: int
    start_time: str
    end_time: str

    model_config = {"from_attributes": True}
