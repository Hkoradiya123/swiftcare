from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.utils.time import utcnow


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def _issue_tokens(self, user: User) -> TokenResponse:
        settings = get_settings()
        access = create_access_token(user_id=user.id, role=user.role)
        raw, hashed = create_refresh_token()
        rt = RefreshToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
        self.db.add(rt)
        await self.db.commit()
        return TokenResponse(access_token=access, refresh_token=raw)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        if await self.repo.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.PATIENT.value,
        )
        user = await self.repo.create(user)
        await self.db.commit()
        return await self._issue_tokens(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")
        return await self._issue_tokens(user)

    async def refresh(self, raw_token: str) -> TokenResponse:
        hashed = hash_refresh_token(raw_token)
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hashed)
        )
        rt = result.scalar_one_or_none()
        if not rt or rt.revoked or rt.expires_at < utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

        rt.revoked = True  # rotate: old token invalidated
        user_result = await self.db.execute(select(User).where(User.id == rt.user_id))
        user = user_result.scalar_one()
        return await self._issue_tokens(user)

    async def logout(self, raw_token: str) -> None:
        hashed = hash_refresh_token(raw_token)
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hashed)
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await self.db.commit()
