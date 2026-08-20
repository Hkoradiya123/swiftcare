from decimal import Decimal
from typing import Annotated, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.enums import AllergyType, AllergySeverity, PrescriptionStatus

_MAX_ITEMS = 10


class PrescriptionItemCreate(BaseModel):
    drug_name: str
    dosage_amount: Decimal
    dosage_unit: str
    frequency_per_day: int
    duration_days: int
    instructions: Optional[str] = None

    @field_validator("dosage_amount")
    @classmethod
    def positive_dosage(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("dosage_amount must be positive")
        return v

    @field_validator("frequency_per_day", "duration_days")
    @classmethod
    def positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be positive")
        return v


class PrescriptionCreate(BaseModel):
    appointment_id: int
    patient_id: int
    items: Annotated[list[PrescriptionItemCreate], Field(min_length=1, max_length=_MAX_ITEMS)]
    notes: Optional[str] = None


class PrescriptionItemRead(BaseModel):
    id: int
    prescription_id: int
    drug_name: str
    dosage_amount: Decimal
    dosage_unit: str
    frequency_per_day: int
    duration_days: int
    instructions: Optional[str]

    model_config = {"from_attributes": True}


class PrescriptionRead(BaseModel):
    id: int
    appointment_id: int
    provider_id: int
    patient_id: int
    status: str
    notes: Optional[str]
    items: list[PrescriptionItemRead]
    created_at: str

    model_config = {"from_attributes": True}


class AllergyCreate(BaseModel):
    patient_id: int
    allergen: str
    allergy_type: AllergyType
    severity: AllergySeverity
    reaction: Optional[str] = None
    recorded_by_id: Optional[int] = None


class AllergyRead(BaseModel):
    id: int
    patient_id: int
    allergen: str
    allergy_type: str
    severity: str
    reaction: Optional[str]
    recorded_by_id: Optional[int]

    model_config = {"from_attributes": True}
