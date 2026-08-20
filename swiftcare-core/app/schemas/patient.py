from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator


class PatientCreate(BaseModel):
    date_of_birth: date
    phone: str
    blood_group: Optional[str] = None
    address: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        digits = v.replace("+", "").replace("-", "").replace(" ", "")
        if not digits.isdigit() or len(digits) < 7:
            raise ValueError("Invalid phone number")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth cannot be today or future")
        return v


class PatientUpdate(BaseModel):
    phone: Optional[str] = None
    blood_group: Optional[str] = None
    address: Optional[str] = None


class PatientRead(BaseModel):
    id: int
    user_id: int
    date_of_birth: date
    phone: str
    blood_group: Optional[str] = None
    address: Optional[str] = None
    full_name: str
    email: str

    model_config = {"from_attributes": True}
