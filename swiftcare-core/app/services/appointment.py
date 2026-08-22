from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
try:
    from swiftcare_contracts.events import AppointmentCompletedEvent, AppointmentScheduledEvent
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    contracts_dir = str(Path(__file__).resolve().parents[3])
    if contracts_dir not in sys.path:
        sys.path.append(contracts_dir)
    from swiftcare_contracts.events import AppointmentCompletedEvent, AppointmentScheduledEvent

from app.models.appointment import Appointment, DomainError, InPersonAppointment, TelehealthAppointment
from app.models.enums import AppointmentType
from app.models.patient import Patient
from app.models.provider import Provider
from app.models.user import User
from app.repositories.appointment import AppointmentRepository
from app.schemas.appointment import AppointmentCreate, AppointmentFilter
from app.events.publisher import publish


class AppointmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AppointmentRepository(db)

    async def create(self, data: AppointmentCreate) -> Appointment:
        if await self.repo.has_overlap(data.provider_id, data.scheduled_start, data.scheduled_end):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider is already booked during this time slot")

        cls = InPersonAppointment if data.appointment_type == AppointmentType.IN_PERSON else TelehealthAppointment
        appt = cls(
            patient_id=data.patient_id,
            provider_id=data.provider_id,
            scheduled_start=data.scheduled_start,
            scheduled_end=data.scheduled_end,
            reason=data.reason,
            notes=data.notes,
            room_number=data.room_number,
            meeting_link=data.meeting_link,
        )
        try:
            await self.repo.create(appt)
            await self.db.commit()
        except IntegrityError as e:
            await self.db.rollback()
            if "ex_appt_no_provider_overlap" in str(e):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider was booked by another user. Please choose another slot.")
            raise

        patient_row = (await self.db.execute(
            select(Patient).options(joinedload(Patient.user)).where(Patient.id == appt.patient_id)
        )).scalar_one()
        provider_row = (await self.db.execute(
            select(Provider).options(joinedload(Provider.user)).where(Provider.id == appt.provider_id)
        )).scalar_one()
        await publish(AppointmentScheduledEvent(
            event_id=uuid4(),
            appointment_id=appt.id,
            patient_id=appt.patient_id,
            provider_id=appt.provider_id,
            scheduled_start=appt.scheduled_start,
            reason=appt.reason,
            patient_name=patient_row.user.full_name,
            patient_email=patient_row.user.email,
            provider_name=provider_row.user.full_name,
        ))
        return appt

    async def _fetch(self, appt_id: int) -> Appointment:
        appt = await self.repo.get_by_id(appt_id)
        if not appt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        return appt

    async def get(self, appt_id: int, current_user: User) -> Appointment:
        appt = await self._fetch(appt_id)

        if current_user.role == "admin":
            return appt

        if current_user.role == "patient":
            from app.repositories.patient import PatientRepository
            patient = await PatientRepository(self.db).get_by_user_id(current_user.id)
            if not patient or appt.patient_id != patient.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        elif current_user.role == "provider":
            from app.repositories.provider import ProviderRepository
            provider = await ProviderRepository(self.db).get_by_user_id(current_user.id)
            if not provider or appt.provider_id != provider.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        return appt

    async def list(self, f: AppointmentFilter, current_user: User) -> list[Appointment]:
        offset = (f.page - 1) * f.page_size

        forced_patient_id = f.patient_id
        forced_provider_id = f.provider_id

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

        return await self.repo.list_filtered(
            provider_id=forced_provider_id,
            patient_id=forced_patient_id,
            status=f.status.value if f.status else None,
            date=f.date,
            offset=offset,
            limit=f.page_size,
        )

    async def check_in(self, appt_id: int) -> Appointment:
        appt = await self._fetch(appt_id)
        try:
            appt.check_in()
        except DomainError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.db.commit()
        return appt

    async def complete(self, appt_id: int) -> Appointment:
        appt = await self._fetch(appt_id)
        try:
            appt.complete()
        except DomainError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.db.commit()

        patient_row = (await self.db.execute(
            select(Patient).options(joinedload(Patient.user)).where(Patient.id == appt.patient_id)
        )).scalar_one()
        provider_row = (await self.db.execute(
            select(Provider).options(joinedload(Provider.user)).where(Provider.id == appt.provider_id)
        )).scalar_one()

        await publish(AppointmentCompletedEvent(
            event_id=uuid4(),
            appointment_id=appt.id,
            patient_id=appt.patient_id,
            provider_id=appt.provider_id,
            completed_at=appt.completed_at,
            patient_name=patient_row.user.full_name,
            patient_email=patient_row.user.email,
            provider_name=provider_row.user.full_name,
            reason=appt.reason,
            notes=appt.notes,
        ))
        return appt

    async def cancel(self, appt_id: int) -> Appointment:
        appt = await self._fetch(appt_id)
        try:
            appt.cancel()
        except DomainError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.db.commit()
        return appt
