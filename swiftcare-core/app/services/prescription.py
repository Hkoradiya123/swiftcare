from datetime import timezone, datetime
from typing import Optional
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

try:
    from swiftcare_contracts.events import PrescriptionCreatedEvent
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    contracts_dir = str(Path(__file__).resolve().parents[3])
    if contracts_dir not in sys.path:
        sys.path.append(contracts_dir)
    from swiftcare_contracts.events import PrescriptionCreatedEvent

from app.events.publisher import publish
from app.models.allergy import Allergy
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, PrescriptionStatus
from app.models.patient import Patient
from app.models.prescription import Prescription, PrescriptionItem
from app.models.provider import Provider
from app.models.user import User
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

        patient_row = (await self.db.execute(
            select(Patient).options(joinedload(Patient.user)).where(Patient.id == data.patient_id)
        )).scalar_one()
        provider_row = (await self.db.execute(
            select(Provider).options(joinedload(Provider.user)).where(Provider.id == provider_id)
        )).scalar_one()
        await publish(PrescriptionCreatedEvent(
            event_id=uuid4(),
            prescription_id=rx.id,
            patient_id=data.patient_id,
            provider_id=provider_id,
            created_at=datetime.now(timezone.utc),
            patient_name=patient_row.user.full_name,
            patient_email=patient_row.user.email,
            provider_name=provider_row.user.full_name,
            drug_names=[item.drug_name for item in data.items],
        ))

        return await self.repo.get_by_id(rx.id)

    async def get(self, rx_id: int, current_user: User) -> Prescription:
        rx = await self.repo.get_by_id(rx_id)
        if not rx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found")
        if current_user.role == "admin":
            return rx
        if current_user.role == "patient":
            from app.repositories.patient import PatientRepository
            patient = await PatientRepository(self.db).get_by_user_id(current_user.id)
            if not patient or rx.patient_id != patient.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        elif current_user.role == "provider":
            from app.repositories.provider import ProviderRepository
            provider = await ProviderRepository(self.db).get_by_user_id(current_user.id)
            if not provider or rx.provider_id != provider.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return rx

    async def list_all(
        self,
        current_user: User,
        patient_id: Optional[int] = None,
        provider_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Prescription]:
        forced_patient_id = patient_id
        forced_provider_id = provider_id
        if current_user.role == "patient":
            from app.repositories.patient import PatientRepository
            patient = await PatientRepository(self.db).get_by_user_id(current_user.id)
            if not patient:
                return []
            forced_patient_id = patient.id
        elif current_user.role == "provider":
            from app.repositories.provider import ProviderRepository
            provider = await ProviderRepository(self.db).get_by_user_id(current_user.id)
            if not provider:
                return []
            forced_provider_id = provider.id
        return await self.repo.list_all(
            patient_id=forced_patient_id,
            provider_id=forced_provider_id,
            appointment_id=appointment_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

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
