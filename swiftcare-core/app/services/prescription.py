from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.allergy import Allergy
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, PrescriptionStatus
from app.models.prescription import Prescription, PrescriptionItem
from app.repositories.appointment import AppointmentRepository
from app.repositories.prescription import AllergyRepository, PrescriptionRepository
from app.schemas.prescription import AllergyCreate, PrescriptionCreate


class PrescriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PrescriptionRepository(db)
        self.allergy_repo = AllergyRepository(db)
        self.appt_repo = AppointmentRepository(db)

    async def create(self, provider_id: int, data: PrescriptionCreate) -> Prescription:
        appt = await self.appt_repo.get_by_id(data.appointment_id)
        if not appt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        if appt.status != AppointmentStatus.COMPLETED.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prescription can only be created for completed appointments")
        if appt.provider_id != provider_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only prescribe for your own appointments")

        known_allergens = await self.allergy_repo.allergen_names(data.patient_id)
        conflicts = [item.drug_name for item in data.items if item.drug_name.strip().lower() in known_allergens]
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient has known allergy to: {', '.join(conflicts)}",
            )

        rx = Prescription(
            appointment_id=data.appointment_id,
            provider_id=provider_id,
            patient_id=data.patient_id,
            notes=data.notes,
        )
        self.db.add(rx)
        await self.db.flush()

        for item_data in data.items:
            self.db.add(PrescriptionItem(
                prescription_id=rx.id,
                drug_name=item_data.drug_name,
                dosage_amount=item_data.dosage_amount,
                dosage_unit=item_data.dosage_unit,
                frequency_per_day=item_data.frequency_per_day,
                duration_days=item_data.duration_days,
                instructions=item_data.instructions,
            ))

        await self.db.commit()
        return await self.repo.get_by_id(rx.id)

    async def get(self, rx_id: int) -> Prescription:
        rx = await self.repo.get_by_id(rx_id)
        if not rx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
        return rx

    async def list_for_patient(self, patient_id: int) -> list[Prescription]:
        return await self.repo.list_for_patient(patient_id)

    async def cancel(self, rx_id: int, provider_id: int) -> Prescription:
        rx = await self.get(rx_id)
        if rx.provider_id != provider_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel your own prescriptions")
        if rx.status == PrescriptionStatus.CANCELLED.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prescription is already cancelled")
        rx.status = PrescriptionStatus.CANCELLED.value
        await self.db.commit()
        return await self.repo.get_by_id(rx.id)


class AllergyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AllergyRepository(db)

    async def create(self, data: AllergyCreate) -> Allergy:
        allergy = Allergy(
            patient_id=data.patient_id,
            allergen=data.allergen,
            allergy_type=data.allergy_type.value,
            severity=data.severity.value,
            reaction=data.reaction,
            recorded_by_id=data.recorded_by_id,
        )
        await self.repo.create(allergy)
        await self.db.commit()
        return allergy

    async def list_for_patient(self, patient_id: int) -> list[Allergy]:
        return await self.repo.get_for_patient(patient_id)

    async def delete(self, allergy_id: int) -> None:
        result = await self.db.get(Allergy, allergy_id)
        if not result or result.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergy not found")
        await self.repo.soft_delete(result)
        await self.db.commit()
