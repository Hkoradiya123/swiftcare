from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.prescription import AllergyBody, AllergyCreate, AllergyRead, PrescriptionCreate, PrescriptionRead
from app.services.prescription import AllergyService, PrescriptionService

router = APIRouter(tags=["prescriptions"])


@router.post("/prescriptions", response_model=PrescriptionRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit(max_calls=10, window_seconds=60))])
async def create_prescription(
    data: PrescriptionCreate,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.provider import ProviderRepository
    provider = await ProviderRepository(db).get_by_user_id(current_user.id)
    return await PrescriptionService(db).create(provider.id, data)


@router.get("/prescriptions", response_model=list[PrescriptionRead])
async def list_prescriptions(
    patient_id: Optional[int] = Query(None),
    provider_id: Optional[int] = Query(None),
    appointment_id: Optional[int] = Query(None),
    rx_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await PrescriptionService(db).list_all(
        current_user=current_user,
        patient_id=patient_id,
        provider_id=provider_id,
        appointment_id=appointment_id,
        status_filter=rx_status,
        page=page,
        page_size=page_size,
    )


@router.get("/prescriptions/{rx_id}", response_model=PrescriptionRead)
async def get_prescription(
    rx_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await PrescriptionService(db).get(rx_id, current_user)


@router.get("/patients/{patient_id}/prescriptions", response_model=list[PrescriptionRead])
async def list_patient_prescriptions(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await PrescriptionService(db).list_for_patient(patient_id)


@router.post("/prescriptions/{rx_id}/cancel", response_model=PrescriptionRead)
async def cancel_prescription(
    rx_id: int,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.provider import ProviderRepository
    provider = await ProviderRepository(db).get_by_user_id(current_user.id)
    return await PrescriptionService(db).cancel(rx_id, provider.id)


# ── Allergies (nested under patient) ───────────────────────────────────

@router.post(
    "/patients/{patient_id}/allergies",
    response_model=AllergyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN))],
)
async def create_allergy(
    patient_id: int,
    body: AllergyBody,
    db: AsyncSession = Depends(get_db),
):
    data = AllergyCreate(
        patient_id=patient_id,
        allergen=body.allergen,
        allergy_type=body.allergy_type,
        severity=body.severity,
        reaction=body.reaction,
        recorded_by_id=body.recorded_by_id,
    )
    return await AllergyService(db).create(data)


@router.get("/patients/{patient_id}/allergies", response_model=list[AllergyRead],
            dependencies=[Depends(get_current_user)])
async def list_allergies(patient_id: int, db: AsyncSession = Depends(get_db)):
    return await AllergyService(db).list_for_patient(patient_id)


@router.delete(
    "/patients/{patient_id}/allergies/{allergy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN))],
)
async def delete_allergy(patient_id: int, allergy_id: int, db: AsyncSession = Depends(get_db)):
    await AllergyService(db).delete(allergy_id)
