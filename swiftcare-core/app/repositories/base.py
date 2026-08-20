from typing import Generic, Optional, TypeVar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, id: int) -> Optional[ModelT]:
        result = await self.db.execute(
            select(self.model).where(
                self.model.id == id,
                self.model.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def count(self, *filters) -> int:
        query = select(func.count()).select_from(self.model)
        if hasattr(self.model, "deleted_at"):
            query = query.where(self.model.deleted_at.is_(None))
        if filters:
            query = query.where(*filters)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def soft_delete(self, obj: ModelT) -> None:
        from app.utils.time import utcnow
        if hasattr(obj, "deleted_at"):
            obj.deleted_at = utcnow()
            await self.db.flush()
