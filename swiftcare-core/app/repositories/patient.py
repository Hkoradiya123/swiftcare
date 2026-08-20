from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.patient import Patient
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    model = Patient

    async def get_by_user_id(self, user_id: int) -> Optional[Patient]:
        result = await self.db.execute(
            select(Patient)
            .where(
                Patient.user_id == user_id,
                Patient.deleted_at.is_(None),
            )
            .options(selectinload(Patient.user))
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_user(self, patient_id: int) -> Optional[Patient]:
        result = await self.db.execute(
            select(Patient)
            .where(
                Patient.id == patient_id,
                Patient.deleted_at.is_(None),
            )
            .options(selectinload(Patient.user))
        )
        return result.scalar_one_or_none()

    async def list_all(self, page: int, size: int) -> List[Patient]:
        offset = (page - 1) * size
        result = await self.db.execute(
            select(Patient)
            .where(Patient.deleted_at.is_(None))
            .options(selectinload(Patient.user))
            .order_by(Patient.id)
            .offset(offset)
            .limit(size)
        )
        return list(result.scalars().all())

    async def create(self, patient: Patient) -> Patient:
        self.db.add(patient)
        await self.db.flush()
        await self.db.refresh(patient)
        return patient
