from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


class ProviderOnboard(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    specialization: str = Field(..., max_length=100, json_schema_extra={"example": "Cardiology"})
    license_number: str = Field(..., max_length=50, json_schema_extra={"example": "MED-CARD-99182"})
    consultation_fee: Decimal = Field(..., max_digits=10, decimal_places=2, json_schema_extra={"example": 500.00})
    default_slot_minutes: int = Field(default=30, json_schema_extra={"example": 30})

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name cannot be blank")
        return v

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

    @field_validator("start_time", "end_time")
    @classmethod
    def time_format(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("Time must be in HH:MM format (00:00–23:59)")
        return v


class ProviderAvailabilityUpdate(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def time_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("Time must be in HH:MM format (00:00–23:59)")
        return v


class ProviderAvailabilityRead(BaseModel):
    id: int
    weekday: int
    start_time: str
    end_time: str

    model_config = {"from_attributes": True}
