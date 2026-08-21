import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery
from app.db.models import AppointmentSlot, ReminderLog
from app.mail.sender import send_email

logger = logging.getLogger(__name__)

_WINDOWS = [
    ("24h_before", 24, 10),  # (reminder_type, target_hours, tolerance_minutes)
    ("2h_before",   2,  5),
]


def _window(hours: int, tolerance_min: int):
    now = datetime.now(timezone.utc)
    target = now + timedelta(hours=hours)
    return target - timedelta(minutes=tolerance_min), target + timedelta(minutes=tolerance_min)


async def _try_send_reminder(factory: async_sessionmaker, slot: AppointmentSlot, reminder_type: str) -> None:
    async with factory() as session:
        log = ReminderLog(
            appointment_id=slot.appointment_id,
            patient_email=slot.patient_email,
            reminder_type=reminder_type,
        )
        session.add(log)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            logger.info("Already sent %s for appt %s — skip", reminder_type, slot.appointment_id)
            return

        label = "tomorrow" if reminder_type == "24h_before" else "in 2 hours"
        try:
            await send_email(
                to=slot.patient_email,
                subject=f"Reminder: appointment {label} — SwiftCare",
                body=(
                    f"Hello {slot.patient_name},\n\n"
                    f"You have an appointment with {slot.provider_name} {label} "
                    f"on {slot.scheduled_start.strftime('%Y-%m-%d at %H:%M UTC')}.\n\n"
                    f"Reason: {slot.reason}\n\n— SwiftCare"
                ),
            )
        except Exception as e:
            # ponytail: rollback so UniqueConstraint row is NOT committed — next Beat run retries.
            # Missing reminder > duplicate reminder for a patient.
            logger.warning("Email failed for %s appt %s: %s — will retry next run", reminder_type, slot.appointment_id, e)
            await session.rollback()
            return

        await session.commit()


async def _send_reminders_async(factory: async_sessionmaker | None = None) -> None:
    own_engine = None
    if factory is None:
        from app.core.config import get_settings
        own_engine = create_async_engine(get_settings().database_url)
        factory = async_sessionmaker(bind=own_engine, expire_on_commit=False)

    try:
        for reminder_type, hours, tolerance in _WINDOWS:
            win_start, win_end = _window(hours, tolerance)
            async with factory() as session:
                result = await session.execute(
                    select(AppointmentSlot).where(
                        AppointmentSlot.scheduled_start >= win_start,
                        AppointmentSlot.scheduled_start <= win_end,
                        AppointmentSlot.status == "scheduled",
                        # ponytail: cancel/reschedule events not yet published from core.
                        # AppointmentSlot.status stays "scheduled" until Step 11+ adds
                        # AppointmentCancelledEvent + AppointmentRescheduledEvent handlers.
                    )
                )
                slots = result.scalars().all()

            for slot in slots:
                await _try_send_reminder(factory, slot, reminder_type)
    finally:
        if own_engine:
            await own_engine.dispose()


@celery.task(name="app.tasks.reminders.send_reminders")
def send_reminders() -> None:
    asyncio.run(_send_reminders_async())
