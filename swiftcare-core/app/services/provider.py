from datetime import time
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderAvailability
from app.models.user import User
from app.repositories.provider import ProviderRepository
from app.schemas.common import PaginatedResponse
from app.schemas.provider import (
    ProviderAvailabilityCreate,
    ProviderAvailabilityRead,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
)


def _to_read(provider: Provider) -> ProviderRead:
    return ProviderRead(
        id=provider.id,
        user_id=provider.user_id,
        specialization=provider.specialization,
        license_number=provider.license_number,
        consultation_fee=provider.consultation_fee,
        default_slot_minutes=provider.default_slot_minutes,
        full_name=provider.user.full_name,
        email=provider.user.email,
    )


class ProviderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProviderRepository(db)

    async def create(
        self, data: ProviderCreate, current_user: User
    ) -> ProviderRead:
        existing = await self.repo.get_by_user_id(current_user.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider profile already exists for this user",
            )

        provider = Provider(
            user_id=current_user.id,
            specialization=data.specialization,
            license_number=data.license_number,
            consultation_fee=data.consultation_fee,
            default_slot_minutes=data.default_slot_minutes,
        )
        provider = await self.repo.create(provider)
        await self.db.commit()
        provider = await self.repo.get_by_id_with_user(provider.id)
        return _to_read(provider)

    async def get(self, provider_id: int) -> ProviderRead:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        return _to_read(provider)

    async def list_all(
        self, page: int, size: int, specialization: str | None = None
    ) -> PaginatedResponse[ProviderRead]:
        if specialization:
            providers = await self.repo.get_by_specialization(
                specialization, page, size
            )
            total = await self.repo.count(
                Provider.specialization.ilike(f"%{specialization}%")
            )
        else:
            providers = await self.repo.list_all(page, size)
            total = await self.repo.count()

        pages = -(-total // size) if size > 0 else 0
        return PaginatedResponse(
            items=[_to_read(p) for p in providers],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def add_availability(
        self, provider_id: int, data: ProviderAvailabilityCreate, current_user: User
    ) -> ProviderAvailabilityRead:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Provider can only add availability for their own profile, unless admin
        if provider.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        start = time.fromisoformat(data.start_time)
        end = time.fromisoformat(data.end_time)
        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be after start_time",
            )

        avail = ProviderAvailability(
            provider_id=provider_id,
            weekday=data.weekday,
            start_time=start,
            end_time=end,
        )
        avail = await self.repo.add_availability(avail)
        await self.db.commit()

        return ProviderAvailabilityRead(
            id=avail.id,
            weekday=avail.weekday,
            start_time=str(avail.start_time),
            end_time=str(avail.end_time),
        )
