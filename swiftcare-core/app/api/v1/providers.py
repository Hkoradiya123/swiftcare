from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.provider import (
    ProviderAvailabilityCreate,
    ProviderAvailabilityRead,
    ProviderCreate,
    ProviderRead,
)
from app.services.provider import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.post("", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    return await ProviderService(db).create(data, current_user)


@router.get("", response_model=PaginatedResponse[ProviderRead])
async def list_providers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    specialization: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProviderRead]:
    return await ProviderService(db).list_all(page, size, specialization)


@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    return await ProviderService(db).get(provider_id)


@router.post(
    "/{provider_id}/availability",
    response_model=ProviderAvailabilityRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_availability(
    provider_id: int,
    data: ProviderAvailabilityCreate,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> ProviderAvailabilityRead:
    return await ProviderService(db).add_availability(provider_id, data, current_user)
