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
    avails = []
    if hasattr(provider, "availability") and provider.availability:
        avails = [
            ProviderAvailabilityRead(
                id=a.id,
                weekday=a.weekday,
                start_time=str(a.start_time),
                end_time=str(a.end_time),
            )
            for a in provider.availability
        ]

    return ProviderRead(
        id=provider.id,
        user_id=provider.user_id,
        specialization=provider.specialization,
        license_number=provider.license_number,
        consultation_fee=provider.consultation_fee,
        default_slot_minutes=provider.default_slot_minutes,
        full_name=provider.user.full_name,
        email=provider.user.email,
        availabilities=avails,
    )


class ProviderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProviderRepository(db)

    async def create(
        self, data: ProviderCreate, current_user: User
    ) -> ProviderRead:
        target_user_id = current_user.id

        if current_user.role == "admin" and data.user_id:
            target_user_id = data.user_id
            from app.repositories.user import UserRepository
            user_repo = UserRepository(self.db)
            target_user = await user_repo.get_by_id(target_user_id)
            if not target_user:
                raise HTTPException(status_code=404, detail="Target user not found")
            if target_user.role != "provider":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target user must have role 'provider'",
                )


        existing = await self.repo.get_by_user_id(target_user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider profile already exists for this user",
            )

        provider = Provider(
            user_id=target_user_id,
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

    async def get_me(self, current_user: User) -> ProviderRead:
        provider = await self.repo.get_by_user_id(current_user.id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider profile not found for this user")
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

        existing_shifts = await self.repo.get_availabilities_by_weekday(provider_id, data.weekday)
        for slot in existing_shifts:
            if max(start, slot.start_time) < min(end, slot.end_time):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Availability slot ({data.start_time} - {data.end_time}) overlaps with existing slot ({slot.start_time} - {slot.end_time})",
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

    async def list_availabilities(
        self, provider_id: int
    ) -> list[ProviderAvailabilityRead]:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        availabilities = await self.repo.get_all_availabilities(provider_id)
        return [
            ProviderAvailabilityRead(
                id=a.id,
                weekday=a.weekday,
                start_time=str(a.start_time),
                end_time=str(a.end_time),
            )
            for a in availabilities
        ]

    async def update_availability(
        self,
        provider_id: int,
        slot_id: int,
        data: ProviderAvailabilityUpdate,
        current_user: User,
    ) -> ProviderAvailabilityRead:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        if provider.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        slot = await self.repo.get_availability_by_id(slot_id)
        if not slot or slot.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="Availability slot not found")

        new_weekday = data.weekday if data.weekday is not None else slot.weekday
        new_start = time.fromisoformat(data.start_time) if data.start_time is not None else slot.start_time
        new_end = time.fromisoformat(data.end_time) if data.end_time is not None else slot.end_time

        if new_end <= new_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be after start_time",
            )

        existing_shifts = await self.repo.get_availabilities_by_weekday(provider_id, new_weekday)
        for existing in existing_shifts:
            if existing.id == slot_id:
                continue
            if max(new_start, existing.start_time) < min(new_end, existing.end_time):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Updated availability slot overlaps with existing slot ({existing.start_time} - {existing.end_time})",
                )

        slot.weekday = new_weekday
        slot.start_time = new_start
        slot.end_time = new_end

        slot = await self.repo.update_availability(slot)
        await self.db.commit()

        return ProviderAvailabilityRead(
            id=slot.id,
            weekday=slot.weekday,
            start_time=str(slot.start_time),
            end_time=str(slot.end_time),
        )

    async def delete_availability(
        self, provider_id: int, slot_id: int, current_user: User
    ) -> None:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        if provider.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        slot = await self.repo.get_availability_by_id(slot_id)
        if not slot or slot.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="Availability slot not found")

        await self.repo.delete_availability(slot)
        await self.db.commit()

