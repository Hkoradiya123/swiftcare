from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.schemas.common import PaginatedResponse
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate


def _to_read(patient: Patient) -> PatientRead:
    return PatientRead(
        id=patient.id,
        user_id=patient.user_id,
        date_of_birth=patient.date_of_birth,
        phone=patient.phone,
        blood_group=patient.blood_group,
        address=patient.address,
        full_name=patient.user.full_name,
        email=patient.user.email,
    )


class PatientService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PatientRepository(db)

    async def create(
        self, data: PatientCreate, current_user: User
    ) -> PatientRead:
        # Check if user already has a patient profile
        existing = await self.repo.get_by_user_id(current_user.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient profile already exists for this user",
            )

        patient = Patient(
            user_id=current_user.id,
            date_of_birth=data.date_of_birth,
            phone=data.phone,
            blood_group=data.blood_group,
            address=data.address,
        )
        patient = await self.repo.create(patient)
        await self.db.commit()
        patient = await self.repo.get_by_id_with_user(patient.id)
        return _to_read(patient)

    async def get(self, patient_id: int) -> PatientRead:
        patient = await self.repo.get_by_id_with_user(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return _to_read(patient)

    async def get_me(self, current_user: User) -> PatientRead:
        patient = await self.repo.get_by_user_id(current_user.id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found for this user")
        return _to_read(patient)


    async def list_all(
        self,
        page: int,
        size: int,
        current_user: User,
        provider_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> PaginatedResponse[PatientRead]:
        from app.schemas.patient import AppointmentSummary

        target_provider_id = provider_id

        if current_user.role == "provider":
            from app.repositories.provider import ProviderRepository
            provider = await ProviderRepository(self.db).get_by_user_id(current_user.id)
            if not provider:
                return PaginatedResponse(items=[], total=0, page=page, size=size, pages=0)
            target_provider_id = provider.id

        patients, total, appt_map = await self.repo.list_with_filters(
            page=page,
            size=size,
            provider_id=target_provider_id,
            from_date=from_date,
            to_date=to_date,
        )

        items = []
        for p in patients:
            p_read = _to_read(p)
            if p.id in appt_map:
                p_read.appointments = [
                    AppointmentSummary.model_validate(appt) for appt in appt_map[p.id]
                ]
            items.append(p_read)

        pages = -(-total // size) if size > 0 else 0
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )



    async def update(
        self, patient_id: int, data: PatientUpdate, current_user: User
    ) -> PatientRead:
        patient = await self.repo.get_by_id_with_user(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Patients can only update their own profile, unless current_user is admin
        if (
            patient.user_id != current_user.id
            and current_user.role != "admin"
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        if data.phone is not None:
            patient.phone = data.phone
        if data.blood_group is not None:
            patient.blood_group = data.blood_group
        if data.address is not None:
            patient.address = data.address

        await self.db.commit()
        patient = await self.repo.get_by_id_with_user(patient.id)
        return _to_read(patient)

    async def delete(self, patient_id: int) -> None:
        patient = await self.repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        await self.repo.soft_delete(patient)
        await self.db.commit()
