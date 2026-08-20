from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.prescription import Allergy, Prescription, PrescriptionItem
from app.repositories.base import BaseRepository


class PrescriptionRepository(BaseRepository[Prescription]):
    model = Prescription

    async def get_by_id(self, id: int) -> Optional[Prescription]:
        result = await self.db.execute(
            select(Prescription)
            .where(Prescription.id == id, Prescription.deleted_at.is_(None))
            .options(selectinload(Prescription.items))
        )
        return result.scalar_one_or_none()

    async def list_for_patient(self, patient_id: int) -> list[Prescription]:
        result = await self.db.execute(
            select(Prescription)
            .where(Prescription.patient_id == patient_id, Prescription.deleted_at.is_(None))
            .options(selectinload(Prescription.items))
            .order_by(Prescription.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_appointment(self, appointment_id: int) -> list[Prescription]:
        result = await self.db.execute(
            select(Prescription)
            .where(Prescription.appointment_id == appointment_id, Prescription.deleted_at.is_(None))
            .options(selectinload(Prescription.items))
        )
        return list(result.scalars().all())

    async def create(self, prescription: Prescription) -> Prescription:
        self.db.add(prescription)
        await self.db.flush()
        return prescription


class AllergyRepository(BaseRepository[Allergy]):
    model = Allergy

    async def get_for_patient(self, patient_id: int) -> list[Allergy]:
        result = await self.db.execute(
            select(Allergy).where(Allergy.patient_id == patient_id, Allergy.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def allergen_names(self, patient_id: int) -> set[str]:
        allergies = await self.get_for_patient(patient_id)
        return {a.allergen.lower() for a in allergies}

    async def create(self, allergy: Allergy) -> Allergy:
        self.db.add(allergy)
        await self.db.flush()
        return allergy
