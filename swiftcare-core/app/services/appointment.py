from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, DomainError, InPersonAppointment, TelehealthAppointment
from app.models.enums import AppointmentType
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
        return appt

    async def get(self, appt_id: int) -> Appointment:
        appt = await self.repo.get_by_id(appt_id)
        if not appt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        return appt

    async def list(self, f: AppointmentFilter) -> list[Appointment]:
        offset = (f.page - 1) * f.page_size
        return await self.repo.list_filtered(
            provider_id=f.provider_id,
            status=f.status.value if f.status else None,
            date=f.date,
            offset=offset,
            limit=f.page_size,
        )

    async def check_in(self, appt_id: int) -> Appointment:
        appt = await self.get(appt_id)
        try:
            appt.check_in()
        except DomainError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.db.commit()
        return appt

    async def complete(self, appt_id: int) -> Appointment:
        appt = await self.get(appt_id)
        try:
            appt.complete()
        except DomainError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.db.commit()
        await publish("appointment.completed", {"appointment_id": appt.id, "patient_id": appt.patient_id})
        return appt

    async def cancel(self, appt_id: int) -> Appointment:
        appt = await self.get(appt_id)
        try:
            appt.cancel()
        except DomainError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await self.db.commit()
        return appt
