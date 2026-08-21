import logging
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from swiftcare_contracts.events import AppointmentCompletedEvent, AppointmentScheduledEvent, PrescriptionCreatedEvent

from app.core.config import get_settings
from app.db.models import AppointmentSlot, DocumentRecord
from app.documents.renderer import render_visit_summary_pdf
from app.mail.sender import send_email
from app.storage.s3 import generate_presigned_url, get_s3_client, upload_pdf

logger = logging.getLogger(__name__)


async def handle_appointment_completed(event: AppointmentCompletedEvent, session: AsyncSession) -> None:
    settings = get_settings()

    pdf_bytes = render_visit_summary_pdf({
        "patient_name": event.patient_name,
        "provider_name": event.provider_name,
        "appointment_date": event.completed_at.strftime("%Y-%m-%d %H:%M UTC"),
        "reason": event.reason,
        "notes": event.notes,
    })

    s3 = get_s3_client()
    key = f"visit-summaries/{event.patient_id}/{event.appointment_id}_{uuid4().hex[:8]}.pdf"
    upload_pdf(s3, settings.s3_bucket, key, pdf_bytes)

    session.add(DocumentRecord(
        appointment_id=event.appointment_id,
        doc_type="visit_summary",
        s3_bucket=settings.s3_bucket,
        s3_key=key,
    ))
    # session.commit() happens in runner.py after this returns

    # Email is best-effort — S3 upload + DB record must not be lost if SMTP is down
    try:
        url = generate_presigned_url(s3, settings.s3_bucket, key)
        await send_email(
            to=event.patient_email,
            subject="Your visit summary is ready — SwiftCare",
            body=(
                f"Hello {event.patient_name},\n\n"
                f"Your visit summary from {event.completed_at.strftime('%Y-%m-%d')} is ready.\n\n"
                f"Download (expires in 1 hour): {url}\n\n"
                f"— SwiftCare"
            ),
        )
    except Exception as e:
        # ponytail: log-and-continue; Step 9 Celery Beat picks up unsent emails via email_sent flag
        logger.warning("Email delivery failed for appt=%s s3_key=%s: %s", event.appointment_id, key, e)


async def handle_appointment_scheduled(event: AppointmentScheduledEvent, session: AsyncSession) -> None:
    slot = AppointmentSlot(
        appointment_id=event.appointment_id,
        patient_id=event.patient_id,
        patient_name=event.patient_name,
        patient_email=event.patient_email,
        provider_name=event.provider_name,
        scheduled_start=event.scheduled_start,
        reason=event.reason,
    )
    session.add(slot)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        logger.info("AppointmentSlot already exists for appt %s — skip", event.appointment_id)


async def handle_prescription_created(event: PrescriptionCreatedEvent, session: AsyncSession) -> None:
    logger.info(
        "prescription.created received — rx=%s patient=%s (PDF not yet implemented)",
        event.prescription_id, event.patient_id,
    )


_HANDLERS = {
    "appointment.scheduled": (AppointmentScheduledEvent, handle_appointment_scheduled),
    "appointment.completed": (AppointmentCompletedEvent, handle_appointment_completed),
    "prescription.created": (PrescriptionCreatedEvent, handle_prescription_created),
}


async def dispatch(payload: dict, session: AsyncSession) -> None:
    event_type = payload.get("event_type", "")
    schema_version = payload.get("schema_version", 1)

    if event_type not in _HANDLERS:
        logger.warning("Unknown event_type=%s — skipping", event_type)
        return

    if schema_version != 1:
        logger.warning("Unsupported schema_version=%s for %s — skipping", schema_version, event_type)
        return

    model_cls, handler = _HANDLERS[event_type]
    event = model_cls.model_validate(payload)
    await handler(event, session)
