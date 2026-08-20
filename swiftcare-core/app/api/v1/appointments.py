from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.enums import AppointmentStatus, AppointmentType, UserRole
from app.schemas.appointment import AppointmentCreate, AppointmentFilter, AppointmentRead
from app.services.appointment import AppointmentService
from typing import Optional

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN))])
async def create(data: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).create(data)


@router.get("", response_model=list[AppointmentRead],
            dependencies=[Depends(get_current_user)])
async def list_appointments(
    provider_id: Optional[int] = None,
    status: Optional[AppointmentStatus] = None,
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    f = AppointmentFilter(provider_id=provider_id, status=status, date=date, page=page, page_size=page_size)
    return await AppointmentService(db).list(f)


@router.get("/{appt_id}", response_model=AppointmentRead,
            dependencies=[Depends(get_current_user)])
async def get(appt_id: int, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).get(appt_id)


@router.post("/{appt_id}/check-in", response_model=AppointmentRead,
             dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN))])
async def check_in(appt_id: int, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).check_in(appt_id)


@router.post("/{appt_id}/complete", response_model=AppointmentRead,
             dependencies=[Depends(require_role(UserRole.PROVIDER))])
async def complete(appt_id: int, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).complete(appt_id)


@router.post("/{appt_id}/cancel", response_model=AppointmentRead,
             dependencies=[Depends(get_current_user)])
async def cancel(appt_id: int, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).cancel(appt_id)
