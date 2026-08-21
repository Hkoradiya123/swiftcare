from typing import Optional, Union
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
    ProviderAvailabilityUpdate,
    ProviderCreate,
    ProviderRead,
)
from app.services.provider import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=PaginatedResponse[ProviderRead])
async def list_providers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    specialization: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProviderRead]:
    return await ProviderService(db).list_all(page, size, specialization)

@router.post("", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
@router.post("/me", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    current_user: User = Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    return await ProviderService(db).create(data, current_user)


@router.get("/me", response_model=ProviderRead)
async def get_my_provider_profile(
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    return await ProviderService(db).get_me(current_user)


@router.get("/me/availability", response_model=list[ProviderAvailabilityRead])
async def list_my_availabilities(
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderAvailabilityRead]:
    provider = await ProviderService(db).get_me(current_user)
    return await ProviderService(db).list_availabilities(provider.id)


@router.post(
    "/me/availability",
    response_model=Union[ProviderAvailabilityRead, list[ProviderAvailabilityRead]],
    status_code=status.HTTP_201_CREATED,
)
async def add_my_availability(
    data: Union[ProviderAvailabilityCreate, list[ProviderAvailabilityCreate]],
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> Union[ProviderAvailabilityRead, list[ProviderAvailabilityRead]]:
    provider = await ProviderService(db).get_me(current_user)
    if isinstance(data, list):
        return await ProviderService(db).add_availabilities_bulk(provider.id, data, current_user)
    return await ProviderService(db).add_availability(provider.id, data, current_user)


@router.patch("/me/availability/{slot_id}", response_model=ProviderAvailabilityRead)
async def update_my_availability(
    slot_id: int,
    data: ProviderAvailabilityUpdate,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> ProviderAvailabilityRead:
    provider = await ProviderService(db).get_me(current_user)
    return await ProviderService(db).update_availability(provider.id, slot_id, data, current_user)


@router.delete("/me/availability/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_availability(
    slot_id: int,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> None:
    provider = await ProviderService(db).get_me(current_user)
    await ProviderService(db).delete_availability(provider.id, slot_id, current_user)


@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProviderRead:
    return await ProviderService(db).get(provider_id)


@router.get("/{provider_id}/availability", response_model=list[ProviderAvailabilityRead])
async def list_provider_availabilities(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderAvailabilityRead]:
    return await ProviderService(db).list_availabilities(provider_id)


@router.post(
    "/{provider_id}/availability",
    response_model=Union[ProviderAvailabilityRead, list[ProviderAvailabilityRead]],
    status_code=status.HTTP_201_CREATED,
)
async def add_availability(
    provider_id: int,
    data: Union[ProviderAvailabilityCreate, list[ProviderAvailabilityCreate]],
    current_user: User = Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Union[ProviderAvailabilityRead, list[ProviderAvailabilityRead]]:
    if isinstance(data, list):
        return await ProviderService(db).add_availabilities_bulk(provider_id, data, current_user)
    return await ProviderService(db).add_availability(provider_id, data, current_user)




@router.patch("/{provider_id}/availability/{slot_id}", response_model=ProviderAvailabilityRead)
async def update_availability(
    provider_id: int,
    slot_id: int,
    data: ProviderAvailabilityUpdate,
    current_user: User = Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ProviderAvailabilityRead:
    return await ProviderService(db).update_availability(provider_id, slot_id, data, current_user)


@router.delete("/{provider_id}/availability/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_availability(
    provider_id: int,
    slot_id: int,
    current_user: User = Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ProviderService(db).delete_availability(provider_id, slot_id, current_user)


