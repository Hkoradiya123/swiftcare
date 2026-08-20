from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.provider import Provider, ProviderAvailability
from app.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[Provider]):
    model = Provider

    async def get_by_user_id(self, user_id: int) -> Optional[Provider]:
        result = await self.db.execute(
            select(Provider)
            .where(
                Provider.user_id == user_id,
                Provider.deleted_at.is_(None),
            )
            .options(
                selectinload(Provider.user),
                selectinload(Provider.availability),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_user(self, provider_id: int) -> Optional[Provider]:
        result = await self.db.execute(
            select(Provider)
            .where(
                Provider.id == provider_id,
                Provider.deleted_at.is_(None),
            )
            .options(
                selectinload(Provider.user),
                selectinload(Provider.availability),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_specialization(
        self, specialization: str, page: int, size: int
    ) -> List[Provider]:
        offset = (page - 1) * size
        result = await self.db.execute(
            select(Provider)
            .where(
                Provider.specialization.ilike(f"%{specialization}%"),
                Provider.deleted_at.is_(None),
            )
            .options(selectinload(Provider.user))
            .order_by(Provider.id)
            .offset(offset)
            .limit(size)
        )
        return list(result.scalars().all())

    async def list_all(self, page: int, size: int) -> List[Provider]:
        offset = (page - 1) * size
        result = await self.db.execute(
            select(Provider)
            .where(Provider.deleted_at.is_(None))
            .options(selectinload(Provider.user))
            .order_by(Provider.id)
            .offset(offset)
            .limit(size)
        )
        return list(result.scalars().all())

    async def create(self, provider: Provider) -> Provider:
        self.db.add(provider)
        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def add_availability(
        self, avail: ProviderAvailability
    ) -> ProviderAvailability:
        self.db.add(avail)
        await self.db.flush()
        await self.db.refresh(avail)
        return avail
