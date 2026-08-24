from datetime import date
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

    async def list_with_filters(
        self,
        page: int,
        size: int,
        provider_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> tuple[List[Patient], int, dict[int, list]]:
        from sqlalchemy import cast, Date, func
        from app.models.appointment import Appointment

        offset = (page - 1) * size
        has_appt_filter = (provider_id is not None) or (from_date is not None) or (to_date is not None)

        if has_appt_filter:
            stmt = select(Patient).join(Appointment, Appointment.patient_id == Patient.id)
            count_stmt = select(func.count(func.distinct(Patient.id))).join(
                Appointment, Appointment.patient_id == Patient.id
            )
            filters = [Patient.deleted_at.is_(None), Appointment.deleted_at.is_(None)]
            if provider_id is not None:
                filters.append(Appointment.provider_id == provider_id)
            if from_date is not None:
                filters.append(cast(Appointment.scheduled_start, Date) >= from_date)
            if to_date is not None:
                filters.append(cast(Appointment.scheduled_start, Date) <= to_date)

            stmt = (stmt.where(*filters).distinct().options(selectinload(Patient.user))
                    .order_by(Patient.id).offset(offset).limit(size))
            count_stmt = count_stmt.where(*filters)

            result = await self.db.execute(stmt)
            patients = list(result.scalars().all())
            count_res = await self.db.execute(count_stmt)
            total = count_res.scalar() or 0

            patient_ids = [p.id for p in patients]
            appt_map: dict[int, list] = {}
            if patient_ids:
                appt_stmt = select(Appointment).where(
                    Appointment.patient_id.in_(patient_ids),
                    Appointment.deleted_at.is_(None),
                )
                if provider_id is not None:
                    appt_stmt = appt_stmt.where(Appointment.provider_id == provider_id)
                if from_date is not None:
                    appt_stmt = appt_stmt.where(cast(Appointment.scheduled_start, Date) >= from_date)
                if to_date is not None:
                    appt_stmt = appt_stmt.where(cast(Appointment.scheduled_start, Date) <= to_date)
                appt_res = await self.db.execute(appt_stmt.order_by(Appointment.scheduled_start.desc()))
                for appt in appt_res.scalars().all():
                    appt_map.setdefault(appt.patient_id, []).append(appt)

            return patients, total, appt_map
        else:
            count_stmt = select(func.count(Patient.id)).where(Patient.deleted_at.is_(None))
            result = await self.db.execute(
                select(Patient).where(Patient.deleted_at.is_(None))
                .options(selectinload(Patient.user)).order_by(Patient.id).offset(offset).limit(size)
            )
            patients = list(result.scalars().all())
            count_res = await self.db.execute(count_stmt)
            total = count_res.scalar() or 0
            return patients, total, {}

    async def create(self, patient: Patient) -> Patient:
        self.db.add(patient)
        await self.db.flush()
        await self.db.refresh(patient)
        return patient
