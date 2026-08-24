from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db.engine import AsyncSessionLocal
from app.db.session import get_db
from app.models.enums import AppointmentStatus, AppointmentType, UserRole
from app.models.user import User
from app.models.visit_embedding import VisitEmbedding
from app.schemas.appointment import AppointmentComplete, AppointmentCreate, AppointmentFilter, AppointmentRead
from app.services.appointment import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])


async def _embed_visit_summary(
    visit_summary_id: int, patient_id: int, appointment_id: int, summary: str
) -> None:
    """Background task: embed visit summary + any prescriptions for the appointment."""
    from app.ai.rag.embedder import embed
    from app.repositories.prescription import PrescriptionRepository
    try:
        async with AsyncSessionLocal() as db:
            prescriptions = await PrescriptionRepository(db).list_for_appointment(appointment_id)
            content = summary
            if prescriptions:
                lines = ["\n\nPrescriptions issued:"]
                for rx in prescriptions:
                    for item in rx.items:
                        lines.append(
                            f"- {item.drug_name} {item.dosage_amount}{item.dosage_unit} "
                            f"{item.frequency_per_day}x/day for {item.duration_days} days"
                            + (f" — {item.instructions}" if item.instructions else "")
                        )
                content += "\n".join(lines)

            vector = await embed(content)
            db.add(VisitEmbedding(
                patient_id=patient_id,
                visit_summary_id=visit_summary_id,
                content=content,
                embedding=vector,
            ))
            await db.commit()
    except Exception:
        pass  # embedding failure must never affect the completed appointment


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN, UserRole.PATIENT))])
async def create(data: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).create(data)


@router.get("", response_model=list[AppointmentRead])
async def list_appointments(
    provider_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[AppointmentStatus] = None,
    date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    f = AppointmentFilter(
        provider_id=provider_id,
        patient_id=patient_id,
        status=status,
        date=date,
        page=page,
        page_size=page_size,
    )
    return await AppointmentService(db).list(f, current_user)


@router.get("/{appt_id}", response_model=AppointmentRead)
async def get(
    appt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AppointmentService(db).get(appt_id, current_user)


@router.post("/{appt_id}/check-in", response_model=AppointmentRead,
             dependencies=[Depends(require_role(UserRole.PROVIDER, UserRole.ADMIN))])
async def check_in(appt_id: int, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).check_in(appt_id)


@router.post("/{appt_id}/complete", response_model=AppointmentRead,
             dependencies=[Depends(require_role(UserRole.PROVIDER))])
async def complete(
    appt_id: int,
    body: AppointmentComplete,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    appt, vs_id = await AppointmentService(db).complete(appt_id, body.summary, body.diagnosis)
    background_tasks.add_task(_embed_visit_summary, vs_id, appt.patient_id, appt_id, body.summary)
    return appt


@router.post("/{appt_id}/cancel", response_model=AppointmentRead,
             dependencies=[Depends(get_current_user)])
async def cancel(appt_id: int, db: AsyncSession = Depends(get_db)):
    return await AppointmentService(db).cancel(appt_id)
