from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_serializer, field_validator




class ProviderCreate(BaseModel):
    specialization: str = Field(..., max_length=100, json_schema_extra={"example": "Cardiology"})
    license_number: str = Field(..., max_length=50, json_schema_extra={"example": "MED-CARD-99182"})
    consultation_fee: Decimal = Field(..., max_digits=10, decimal_places=2, json_schema_extra={"example": 500.00})
    default_slot_minutes: int = Field(default=30, json_schema_extra={"example": 30})
    user_id: Optional[int] = Field(default=None, json_schema_extra={"example": 42})

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
    consultation_fee: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=2)
    default_slot_minutes: Optional[int] = None


class ProviderRead(BaseModel):
    id: int = Field(..., json_schema_extra={"example": 1})
    user_id: int = Field(..., json_schema_extra={"example": 5})
    specialization: str = Field(..., json_schema_extra={"example": "Cardiology"})
    license_number: str = Field(..., json_schema_extra={"example": "MED-CARD-99182"})
    consultation_fee: Decimal = Field(..., max_digits=10, decimal_places=2, json_schema_extra={"example": 500.00})
    default_slot_minutes: int = Field(..., json_schema_extra={"example": 30})
    full_name: str = Field(..., json_schema_extra={"example": "Dr. Anjali Mehta"})
    email: str = Field(..., json_schema_extra={"example": "dr.anjali@swiftcare.io"})
    availabilities: Optional[list["ProviderAvailabilityRead"]] = None

    @field_serializer("consultation_fee")
    def serialize_consultation_fee(self, v: Decimal) -> str:
        return f"{v:.2f}"

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,    
                "user_id": 5,
                "specialization": "Cardiology",
                "license_number": "MED-CARD-99182",
                "consultation_fee": 500.00,
                "default_slot_minutes": 30,
                "full_name": "Dr. Anjali Mehta",
                "email": "dr.anjali@swiftcare.io",
                "availabilities": [
                    {
                        "id": 1,
                        "weekday": 0,
                        "start_time": "09:00:00",
                        "end_time": "17:00:00"
                    }
                ]
            }
        }
    }




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
    weekday: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @field_validator("weekday")
    @classmethod
    def weekday_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in range(7):
            raise ValueError("Weekday must be between 0 and 6")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
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

