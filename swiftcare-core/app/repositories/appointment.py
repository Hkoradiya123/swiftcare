from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus
from app.repositories.base import BaseRepository


_INACTIVE = (AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value)


class AppointmentRepository(BaseRepository[Appointment]):
    model = Appointment

    async def has_overlap(self, provider_id: int, start: datetime, end: datetime, exclude_id: Optional[int] = None) -> bool:
        stmt = select(Appointment.id).where(
            Appointment.provider_id == provider_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.not_in(_INACTIVE),
            Appointment.scheduled_start < end,
            Appointment.scheduled_end > start,
        )
        if exclude_id:
            stmt = stmt.where(Appointment.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.first() is not None

    async def has_appointment_with_patient(self, provider_id: int, patient_id: int) -> bool:
        stmt = select(Appointment.id).where(
            Appointment.provider_id == provider_id,
            Appointment.patient_id == patient_id,
            Appointment.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.first() is not None

    async def list_filtered(
        self,
        provider_id: Optional[int],
        status: Optional[str],
        date: Optional[str],
        offset: int,
        limit: int,
        patient_id: Optional[int] = None,
    ) -> list[Appointment]:
        stmt = select(Appointment).where(Appointment.deleted_at.is_(None))
        if provider_id:
            stmt = stmt.where(Appointment.provider_id == provider_id)
        if patient_id:
            stmt = stmt.where(Appointment.patient_id == patient_id)
        if status:
            stmt = stmt.where(Appointment.status == status)
        if date:
            stmt = stmt.where(Appointment.scheduled_start.cast(str).startswith(date))
        stmt = stmt.order_by(Appointment.scheduled_start).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, appointment: Appointment) -> Appointment:
        self.db.add(appointment)
        await self.db.flush()
        return appointment
