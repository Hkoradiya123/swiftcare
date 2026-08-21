import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from freezegun import freeze_time
from sqlalchemy import select

from app.db.models import AppointmentSlot, ReminderLog
from app.tasks.reminders import _send_reminders_async


_NOW = datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc)


def _slot(appt_id: int, hours_from_now: float, status: str = "scheduled") -> AppointmentSlot:
    return AppointmentSlot(
        appointment_id=appt_id,
        patient_id=appt_id,
        patient_name="Jane Smith",
        patient_email=f"jane{appt_id}@example.com",
        provider_name="Dr. Reed",
        scheduled_start=_NOW + timedelta(hours=hours_from_now),
        reason="Annual checkup",
        status=status,
    )


@pytest.mark.asyncio
async def test_24h_reminder_sent_once_idempotent(session_factory):
    """
    Two runs of send_reminders when appointment is in the 24h window.
    Email sent exactly once — UniqueConstraint prevents the duplicate.
    """
    async with session_factory() as session:
        session.add(_slot(appt_id=1, hours_from_now=24))
        await session.commit()

    with (
        freeze_time(_NOW),
        patch("app.tasks.reminders.send_email", new_callable=AsyncMock) as mock_email,
    ):
        await _send_reminders_async(session_factory)
        assert mock_email.call_count == 1

        await _send_reminders_async(session_factory)
        assert mock_email.call_count == 1  # second run: IntegrityError → skip

    async with session_factory() as session:
        result = await session.execute(select(ReminderLog))
        logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].reminder_type == "24h_before"


@pytest.mark.asyncio
async def test_both_reminders_sent_at_different_times(session_factory):
    """
    Same appointment: 24h reminder fires when 24h away, 2h reminder fires when 2h away.
    Two separate ReminderLog entries, two emails total.
    """
    async with session_factory() as session:
        session.add(_slot(appt_id=2, hours_from_now=24))
        await session.commit()

    with (
        patch("app.tasks.reminders.send_email", new_callable=AsyncMock) as mock_email,
    ):
        with freeze_time(_NOW):  # appointment is exactly 24h away
            await _send_reminders_async(session_factory)
        assert mock_email.call_count == 1

        with freeze_time(_NOW + timedelta(hours=22)):  # appointment is now 2h away
            await _send_reminders_async(session_factory)
        assert mock_email.call_count == 2

    async with session_factory() as session:
        result = await session.execute(
            select(ReminderLog).where(ReminderLog.appointment_id == 2).order_by(ReminderLog.reminder_type)
        )
        logs = result.scalars().all()
    assert len(logs) == 2
    assert {l.reminder_type for l in logs} == {"24h_before", "2h_before"}


@pytest.mark.asyncio
async def test_cancelled_appointment_skipped(session_factory):
    """
    Appointment with status='cancelled' must not receive any reminders.
    """
    async with session_factory() as session:
        session.add(_slot(appt_id=3, hours_from_now=24, status="cancelled"))
        await session.commit()

    with (
        freeze_time(_NOW),
        patch("app.tasks.reminders.send_email", new_callable=AsyncMock) as mock_email,
    ):
        await _send_reminders_async(session_factory)

    assert mock_email.call_count == 0

    async with session_factory() as session:
        result = await session.execute(select(ReminderLog))
        assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_email_failure_retries_next_run(session_factory):
    """
    SMTP down on first run → ReminderLog NOT committed (rolled back) → appointment NOT permanently lost.
    Second run: no existing log → tries again → email succeeds this time.
    Missing reminder is worse than a duplicate for patients.
    """
    async with session_factory() as session:
        session.add(_slot(appt_id=4, hours_from_now=24))
        await session.commit()

    with (
        freeze_time(_NOW),
        patch("app.tasks.reminders.send_email", new_callable=AsyncMock, side_effect=Exception("SMTP down")),
    ):
        await _send_reminders_async(session_factory)  # must not raise

    # Row not committed — no log entry
    async with session_factory() as session:
        result = await session.execute(
            select(ReminderLog).where(ReminderLog.appointment_id == 4)
        )
        assert result.scalars().all() == []

    # Second run — SMTP up now, reminder goes through
    with (
        freeze_time(_NOW),
        patch("app.tasks.reminders.send_email", new_callable=AsyncMock) as mock_retry,
    ):
        await _send_reminders_async(session_factory)

    assert mock_retry.call_count == 1  # retried and succeeded
