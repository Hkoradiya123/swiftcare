from datetime import timedelta
from uuid import uuid4
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
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, TokenResponse
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

    async def forgot_password(self, data: ForgotPasswordRequest) -> None:
        import hashlib, secrets
        from app.events.publisher import publish
        from swiftcare_contracts.events import PasswordResetRequestedEvent

        user = await self.repo.get_by_email(data.email)
        if not user:
            return  # silent — don't leak whether email exists

        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()

        prt = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + timedelta(hours=1),
        )
        self.db.add(prt)
        await self.db.commit()

        # best-effort — token already saved; if Redis is down the email just won't send
        try:
            await publish(PasswordResetRequestedEvent(
                event_id=uuid4(),
                user_email=user.email,
                user_name=user.full_name,
                reset_token=raw,
            ))
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Redis unavailable — password reset email not queued for %s", user.email
            )

    async def change_password(self, user: User, data: ChangePasswordRequest) -> None:
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        user.hashed_password = hash_password(data.new_password)
        await self.db.commit()

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        import hashlib
        token_hash = hashlib.sha256(data.token.encode()).hexdigest()

        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        prt = result.scalar_one_or_none()

        if not prt or prt.used or prt.expires_at < utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

        user_result = await self.db.execute(select(User).where(User.id == prt.user_id))
        user = user_result.scalar_one()
        user.hashed_password = hash_password(data.new_password)
        prt.used = True
        await self.db.commit()
