from datetime import date, datetime, time, timedelta
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
    ProviderOnboard,
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

    async def onboard(self, data: ProviderOnboard) -> ProviderRead:
        from app.core.security import hash_password
        from app.models.enums import UserRole
        from app.repositories.user import UserRepository

        user_repo = UserRepository(self.db)
        if await user_repo.get_by_email(data.email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.PROVIDER.value,
        )
        user = await user_repo.create(user)
        await self.db.flush()

        existing = await self.repo.get_by_user_id(user.id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider profile already exists")

        provider = Provider(
            user_id=user.id,
            specialization=data.specialization,
            license_number=data.license_number,
            consultation_fee=data.consultation_fee,
            default_slot_minutes=data.default_slot_minutes,
        )
        provider = await self.repo.create(provider)
        await self.db.commit()
        provider = await self.repo.get_by_id_with_user(provider.id)
        return _to_read(provider)

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

    async def get_me(self, current_user: User) -> ProviderRead:
        provider = await self.repo.get_by_user_id(current_user.id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider profile not found for this user")
        return _to_read(provider)

    async def update(self, provider_id: int, data: ProviderUpdate, current_user: User) -> ProviderRead:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if current_user.role != "admin" and provider.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        if data.specialization is not None:
            provider.specialization = data.specialization
        if data.consultation_fee is not None:
            if data.consultation_fee <= 0:
                raise HTTPException(status_code=400, detail="Fee must be positive")
            provider.consultation_fee = data.consultation_fee
        if data.default_slot_minutes is not None:
            if data.default_slot_minutes not in (15, 20, 30, 45, 60):
                raise HTTPException(status_code=400, detail="Slot must be 15/20/30/45/60 minutes")
            provider.default_slot_minutes = data.default_slot_minutes
        await self.db.commit()
        provider = await self.repo.get_by_id_with_user(provider_id)
        return _to_read(provider)

    async def add_availabilities_bulk(
        self, provider_id: int, data_list: list[ProviderAvailabilityCreate], current_user: User
    ) -> list[ProviderAvailabilityRead]:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if provider.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        parsed_items = []
        for idx, item in enumerate(data_list):
            start = time.fromisoformat(item.start_time)
            end = time.fromisoformat(item.end_time)
            if end <= start:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item {idx}: end_time must be after start_time")
            parsed_items.append((item, start, end))

        for i in range(len(parsed_items)):
            item1, s1, e1 = parsed_items[i]
            for j in range(i + 1, len(parsed_items)):
                item2, s2, e2 = parsed_items[j]
                if item1.weekday == item2.weekday and max(s1, s2) < min(e1, e2):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Batch payload contains overlapping slots")

        created: list[ProviderAvailability] = []
        for item, start, end in parsed_items:
            existing = await self.repo.get_availabilities_by_weekday(provider_id, item.weekday)
            for slot in existing:
                if max(start, slot.start_time) < min(end, slot.end_time):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Slot overlaps with existing ({slot.start_time} - {slot.end_time})")
            avail = ProviderAvailability(provider_id=provider_id, weekday=item.weekday, start_time=start, end_time=end)
            avail = await self.repo.add_availability(avail)
            created.append(avail)

        await self.db.commit()
        return [ProviderAvailabilityRead(id=a.id, weekday=a.weekday, start_time=str(a.start_time), end_time=str(a.end_time)) for a in created]

    async def list_availabilities(self, provider_id: int) -> list[ProviderAvailabilityRead]:
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        availabilities = await self.repo.get_all_availabilities(provider_id)
        return [
            ProviderAvailabilityRead(id=a.id, weekday=a.weekday, start_time=str(a.start_time), end_time=str(a.end_time))
            for a in availabilities
        ]

    async def update_availability(
        self, provider_id: int, slot_id: int, data: "ProviderAvailabilityUpdate", current_user: User
    ) -> ProviderAvailabilityRead:
        from app.schemas.provider import ProviderAvailabilityUpdate
        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if provider.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        slot = await self.repo.get_availability_by_id(slot_id)
        if not slot or slot.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="Availability slot not found")
        new_start = time.fromisoformat(data.start_time) if data.start_time is not None else slot.start_time
        new_end = time.fromisoformat(data.end_time) if data.end_time is not None else slot.end_time
        if new_end <= new_start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time must be after start_time")
        existing = await self.repo.get_availabilities_by_weekday(provider_id, slot.weekday)
        for s in existing:
            if s.id == slot_id:
                continue
            if max(new_start, s.start_time) < min(new_end, s.end_time):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Updated slot overlaps with existing slot")
        slot.start_time = new_start
        slot.end_time = new_end
        slot = await self.repo.update_availability(slot)
        await self.db.commit()
        return ProviderAvailabilityRead(id=slot.id, weekday=slot.weekday, start_time=str(slot.start_time), end_time=str(slot.end_time))

    async def get_open_slots(self, provider_id: int, date_str: str) -> list[dict]:
        from app.repositories.appointment import AppointmentRepository

        provider = await self.repo.get_by_id_with_user(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

        weekday = target_date.weekday()  # 0=Monday
        schedule = await self.repo.get_availabilities_by_weekday(provider_id, weekday)
        if not schedule:
            return []

        slot_minutes = provider.default_slot_minutes
        booked = await AppointmentRepository(self.db).list_filtered(
            provider_id=provider_id, status=None, date=date_str, offset=0, limit=200
        )
        booked_ranges = [(a.scheduled_start, a.scheduled_end) for a in booked]

        open_slots = []
        for shift in schedule:
            cursor = datetime.combine(target_date, shift.start_time)
            end_of_shift = datetime.combine(target_date, shift.end_time)
            while cursor + timedelta(minutes=slot_minutes) <= end_of_shift:
                slot_end = cursor + timedelta(minutes=slot_minutes)
                overlap = any(s < slot_end and cursor < e for s, e in booked_ranges)
                if not overlap:
                    open_slots.append({
                        "start": cursor.isoformat(),
                        "end": slot_end.isoformat(),
                    })
                cursor = slot_end

        return open_slots

    async def delete_availability(self, provider_id: int, slot_id: int, current_user: User) -> None:
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

        existing = await self.repo.get_availabilities_by_weekday(provider_id, data.weekday)
        for slot in existing:
            if max(start, slot.start_time) < min(end, slot.end_time):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Availability slot overlaps with existing slot ({slot.start_time} - {slot.end_time})",
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
