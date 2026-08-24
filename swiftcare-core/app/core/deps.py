from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token or expired session",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))

    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account inactive",
        )
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of 401 when no token provided."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await UserRepository(db).get_by_id(int(user_id))
        if not user or not user.is_active or user.deleted_at:
            return None
        return user
    except Exception:
        return None


def require_role(*roles: UserRole):
    """
    Factory function for role-based access control.
    
    Usage:
        @router.get("/protected", dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN))])
    """
    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        allowed_values = [r.value for r in roles]
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {allowed_values}",
            )
        return current_user

    return _check_role
