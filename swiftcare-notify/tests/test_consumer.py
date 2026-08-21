import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy import select

from app.consumers.runner import STREAM, GROUP, ensure_group, handle_message
from app.db.models import DocumentRecord


def _appt_payload(event_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "appointment.completed",
        "schema_version": 1,
        "appointment_id": 42,
        "patient_id": 7,
        "provider_id": 3,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "patient_name": "Jane Smith",
        "patient_email": "jane.smith@example.com",
        "provider_name": "Dr. Alan Reed",
        "reason": "Annual checkup",
        "notes": None,
    }


def _encoded(payload: dict) -> dict:
    return {b"data": json.dumps(payload).encode()}


@pytest.mark.asyncio
async def test_duplicate_event_id_processed_only_once(redis_client, session_factory):
    """
    Same event_id delivered twice (XACK-before-crash retry scenario).
    dispatch must be called exactly once — idempotency via processed_events PK.
    """
    event_id = str(uuid4())
    payload = _appt_payload(event_id)
    data = _encoded(payload)

    mock_dispatch = AsyncMock()
    with patch("app.consumers.runner.dispatch", mock_dispatch):
        await handle_message(b"1-0", data, redis_client, session_factory)
        assert mock_dispatch.call_count == 1

        # same event_id, different stream message id (real retry scenario)
        await handle_message(b"2-0", data, redis_client, session_factory)
        assert mock_dispatch.call_count == 1  # ← proof idempotency works


@pytest.mark.asyncio
async def test_handler_failure_does_not_ack(redis_client, session_factory):
    """
    When dispatch raises, XACK must NOT happen — message stays in pending list
    so Redis retries it after consumer restart.
    """
    # Put a real message into the stream and move it to pending via XREADGROUP
    await redis_client.xadd(STREAM, {b"data": b"placeholder"})
    await ensure_group(redis_client)
    msgs = await redis_client.xreadgroup(GROUP, "test-consumer", {STREAM: ">"}, count=1)
    msg_id = msgs[0][1][0][0]

    payload = _appt_payload(str(uuid4()))
    data = _encoded(payload)

    with patch("app.consumers.runner.dispatch", side_effect=Exception("handler failed")):
        with pytest.raises(Exception, match="handler failed"):
            await handle_message(msg_id, data, redis_client, session_factory)

    # XACK was never called — message must still be in the pending list
    pending = await redis_client.xpending(STREAM, GROUP)
    assert pending["pending"] == 1


@pytest.mark.asyncio
async def test_consumer_group_survives_restart(redis_client):
    """
    ensure_group() called twice must not raise.
    Bug this catches: wrong BUSYGROUP string-match (case, prefix) → service
    crashes on every restart after the first deploy when the group already exists.
    """
    await ensure_group(redis_client)
    await ensure_group(redis_client)  # must be silent, not raise


@pytest.mark.asyncio
async def test_handle_appointment_completed_creates_document_record(session_factory):
    """
    PDF render + S3 upload mocked — verifies DocumentRecord is written to DB.
    Email is best-effort so its failure must not prevent the record from being saved.
    """
    from app.consumers.handlers import handle_appointment_completed
    from swiftcare_contracts.events import AppointmentCompletedEvent

    event = AppointmentCompletedEvent.model_validate(_appt_payload(str(uuid4())))

    fake_s3 = MagicMock()
    fake_s3.generate_presigned_url.return_value = "http://minio/presigned"

    with (
        patch("app.consumers.handlers.render_visit_summary_pdf", return_value=b"%PDF-fake"),
        patch("app.consumers.handlers.get_s3_client", return_value=fake_s3),
        patch("app.consumers.handlers.upload_pdf"),
        patch("app.consumers.handlers.generate_presigned_url", return_value="http://minio/presigned"),
        patch("app.consumers.handlers.send_email", new=AsyncMock()),
    ):
        async with session_factory() as session:
            await handle_appointment_completed(event, session)
            await session.commit()

            result = await session.execute(
                select(DocumentRecord).where(DocumentRecord.appointment_id == event.appointment_id)
            )
            doc = result.scalar_one()

    assert doc.doc_type == "visit_summary"
    assert doc.appointment_id == event.appointment_id
    assert "visit-summaries" in doc.s3_key


@pytest.mark.asyncio
async def test_email_failure_does_not_lose_document_record(session_factory):
    """
    SMTP down — DocumentRecord phir bhi DB me hona chahiye.
    Regression guard: agar email call try block se bahar chali gayi to ye test fail karega.
    """
    from app.consumers.handlers import handle_appointment_completed
    from swiftcare_contracts.events import AppointmentCompletedEvent

    event = AppointmentCompletedEvent.model_validate(_appt_payload(str(uuid4())))

    with (
        patch("app.consumers.handlers.render_visit_summary_pdf", return_value=b"%PDF-fake"),
        patch("app.consumers.handlers.get_s3_client", return_value=MagicMock()),
        patch("app.consumers.handlers.upload_pdf"),
        patch("app.consumers.handlers.generate_presigned_url", return_value="http://minio/presigned"),
        patch("app.consumers.handlers.send_email", new=AsyncMock(side_effect=Exception("SMTP timeout"))),
    ):
        async with session_factory() as session:
            await handle_appointment_completed(event, session)  # must not raise
            await session.commit()

            result = await session.execute(
                select(DocumentRecord).where(DocumentRecord.appointment_id == event.appointment_id)
            )
            doc = result.scalar_one()  # fails if record was lost

    assert doc.s3_key is not None
