import logging
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from swiftcare_contracts.events import AppointmentCompletedEvent, AppointmentScheduledEvent, PasswordResetRequestedEvent, PrescriptionCreatedEvent

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
        return

    try:
        await send_email(
            to=event.patient_email,
            subject="Appointment confirmed — SwiftCare",
            body=(
                f"Hello {event.patient_name},\n\n"
                f"Your appointment with {event.provider_name} is confirmed.\n\n"
                f"Date & time: {event.scheduled_start.strftime('%Y-%m-%d at %H:%M UTC')}\n"
                f"Reason: {event.reason}\n\n"
                f"— SwiftCare"
            ),
        )
    except Exception as e:
        logger.warning("Confirmation email failed for appt=%s: %s", event.appointment_id, e)


async def handle_prescription_created(event: PrescriptionCreatedEvent, session: AsyncSession) -> None:
    drugs = ", ".join(event.drug_names) if event.drug_names else "see your account for details"
    try:
        await send_email(
            to=event.patient_email,
            subject="Your prescription is ready — SwiftCare",
            body=(
                f"Hello {event.patient_name},\n\n"
                f"{event.provider_name} has created a prescription for you.\n\n"
                f"Medications: {drugs}\n\n"
                f"Log in to your SwiftCare account to view full details.\n\n"
                f"— SwiftCare"
            ),
        )
    except Exception as e:
        logger.warning("Prescription email failed for rx=%s: %s", event.prescription_id, e)


async def handle_password_reset_requested(event: PasswordResetRequestedEvent, session: AsyncSession) -> None:
    logger.info("Sending password reset email to %s", event.user_email)
    try:
        await send_email(
            to=event.user_email,
            subject="Reset your password — SwiftCare",
            body=(
                f"Hello {event.user_name},\n\n"
                f"Use the token below to reset your password (expires in 1 hour):\n\n"
                f"{event.reset_token}\n\n"
                f"POST /api/v1/auth/reset-password with:\n"
                f'  {{"token": "<above token>", "new_password": "<your new password>"}}\n\n'
                f"If you did not request this, ignore this email.\n\n"
                f"— SwiftCare"
            ),
        )
        logger.info("Password reset email sent to %s", event.user_email)
    except Exception as e:
        logger.warning("Password reset email failed for %s: %s", event.user_email, e)


_HANDLERS = {
    "appointment.scheduled": (AppointmentScheduledEvent, handle_appointment_scheduled),
    "appointment.completed": (AppointmentCompletedEvent, handle_appointment_completed),
    "prescription.created": (PrescriptionCreatedEvent, handle_prescription_created),
    "auth.password_reset_requested": (PasswordResetRequestedEvent, handle_password_reset_requested),
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
