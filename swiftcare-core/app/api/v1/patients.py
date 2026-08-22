from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.patient import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
@router.post("/me", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(
    data: PatientCreate,
    current_user: User = Depends(require_role(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
) -> PatientRead:
    return await PatientService(db).create(data, current_user)


@router.get("/me", response_model=PatientRead)
async def get_my_patient_profile(
    current_user: User = Depends(require_role(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
) -> PatientRead:
    return await PatientService(db).get_me(current_user)


@router.patch("/me", response_model=PatientRead)
async def update_my_patient_profile(
    data: PatientUpdate,
    current_user: User = Depends(require_role(UserRole.PATIENT)),
    db: AsyncSession = Depends(get_db),
) -> PatientRead:
    patient = await PatientService(db).get_me(current_user)
    return await PatientService(db).update(patient.id, data, current_user)


from datetime import date
from typing import Optional


@router.get("", response_model=PaginatedResponse[PatientRead])
async def list_patients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    provider_id: Optional[int] = Query(None, description="Admin filter by provider ID"),
    from_date: Optional[date] = Query(None, description="Filter by appointment start date (from YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Filter by appointment end date (to YYYY-MM-DD)"),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PatientRead]:
    return await PatientService(db).list_all(
        page=page,
        size=size,
        current_user=current_user,
        provider_id=provider_id,
        from_date=from_date,
        to_date=to_date,
    )



@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: int,
    current_user: User = Depends(require_role(UserRole.PATIENT, UserRole.PROVIDER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PatientRead:
    return await PatientService(db).get(patient_id, current_user)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: int,
    data: PatientUpdate,
    current_user: User = Depends(require_role(UserRole.PATIENT, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> PatientRead:
    return await PatientService(db).update(patient_id, data, current_user)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: int,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    await PatientService(db).delete(patient_id)

