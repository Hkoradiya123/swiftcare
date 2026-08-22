from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.allergy import Allergy
from app.models.enums import AllergyType
from app.models.prescription import Prescription, PrescriptionItem
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

    async def list_all(
        self,
        patient_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Prescription]:
        offset = (page - 1) * page_size
        stmt = (
            select(Prescription)
            .where(Prescription.deleted_at.is_(None))
            .options(selectinload(Prescription.items))
            .order_by(Prescription.created_at.desc())
        )
        if patient_id is not None:
            stmt = stmt.where(Prescription.patient_id == patient_id)
        if provider_id is not None:
            stmt = stmt.where(Prescription.provider_id == provider_id)
        if appointment_id is not None:
            stmt = stmt.where(Prescription.appointment_id == appointment_id)
        if status_filter is not None:
            stmt = stmt.where(Prescription.status == status_filter)
        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
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
        result = await self.db.execute(
            select(Allergy.allergen_normalized).where(
                Allergy.patient_id == patient_id,
                Allergy.deleted_at.is_(None),
                Allergy.allergy_type == AllergyType.DRUG.value,
            )
        )
        return {row[0] for row in result.all()}

    async def create(self, allergy: Allergy) -> Allergy:
        self.db.add(allergy)
        await self.db.flush()
        return allergy
