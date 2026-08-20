from pydantic import BaseModel, EmailStr
from app.models.enums import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.PATIENT


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}
