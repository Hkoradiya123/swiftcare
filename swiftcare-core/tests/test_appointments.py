import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from httpx import AsyncClient


def appt_payload(provider_id: int, patient_id: int, start: str, end: str, appt_type: str = "in_person") -> dict:
    return {
        "patient_id": patient_id,
        "provider_id": provider_id,
        "appointment_type": appt_type,
        "scheduled_start": start,
        "scheduled_end": end,
        "reason": "Routine checkup",
    }


@pytest.mark.asyncio
async def test_create_appointment_success(client: AsyncClient, provider_data, patient_data):
    payload = appt_payload(
        provider_data["provider_id"], patient_data["patient_id"],
        "2026-09-01T10:00:00+00:00", "2026-09-01T10:30:00+00:00",
    )
    res = await client.post("/api/v1/appointments", json=payload, headers=provider_data["headers"])
    assert res.status_code == 201
    assert res.json()["status"] == "scheduled"


@pytest.mark.asyncio
async def test_app_level_overlap_returns_409(client: AsyncClient, provider_data, patient_data):
    payload = appt_payload(
        provider_data["provider_id"], patient_data["patient_id"],
        "2026-09-01T10:00:00+00:00", "2026-09-01T10:30:00+00:00",
    )
    res1 = await client.post("/api/v1/appointments", json=payload, headers=provider_data["headers"])
    assert res1.status_code == 201

    # Same slot — app-level check catches it
    res2 = await client.post("/api/v1/appointments", json=payload, headers=provider_data["headers"])
    assert res2.status_code == 409
    assert "booked" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_back_to_back_no_conflict(client: AsyncClient, provider_data, patient_data):
    pid, prid = provider_data["provider_id"], patient_data["patient_id"]
    headers = provider_data["headers"]

    r1 = await client.post("/api/v1/appointments", headers=headers, json=appt_payload(
        pid, prid, "2026-09-01T09:00:00+00:00", "2026-09-01T09:30:00+00:00",
    ))
    r2 = await client.post("/api/v1/appointments", headers=headers, json=appt_payload(
        pid, prid, "2026-09-01T09:30:00+00:00", "2026-09-01T10:00:00+00:00",
    ))
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_db_level_race_conflict_returns_409(client: AsyncClient, provider_data, patient_data):
    """
    Simulates a race: both requests pass the app-level overlap check,
    but the DB exclusion constraint fires on the second insert.
    Proves the IntegrityError → 409 conversion in AppointmentService.create().
    """
    payload = appt_payload(
        provider_data["provider_id"], patient_data["patient_id"],
        "2026-09-02T10:00:00+00:00", "2026-09-02T10:30:00+00:00",
    )
    orig = Exception("DETAIL: conflicts with existing key in constraint ex_appt_no_provider_overlap")
    with patch("app.repositories.appointment.AppointmentRepository.has_overlap",
               new_callable=AsyncMock, return_value=False), \
         patch("app.repositories.appointment.AppointmentRepository.create",
               new_callable=AsyncMock,
               side_effect=SAIntegrityError("INSERT", {}, orig)):
        res = await client.post("/api/v1/appointments", json=payload, headers=provider_data["headers"])
    assert res.status_code == 409
    assert "booked by another user" in res.json()["detail"]


@pytest.mark.asyncio
async def test_patient_cannot_create_appointment_returns_403(client: AsyncClient, provider_data, patient_data):
    payload = appt_payload(
        provider_data["provider_id"], patient_data["patient_id"],
        "2026-09-01T11:00:00+00:00", "2026-09-01T11:30:00+00:00",
    )
    res = await client.post("/api/v1/appointments", json=payload, headers=patient_data["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_checkin_and_complete_flow(client: AsyncClient, provider_data, patient_data):
    payload = appt_payload(
        provider_data["provider_id"], patient_data["patient_id"],
        "2026-09-01T14:00:00+00:00", "2026-09-01T14:30:00+00:00",
    )
    appt_id = (await client.post(
        "/api/v1/appointments", json=payload, headers=provider_data["headers"]
    )).json()["id"]

    ci = await client.post(f"/api/v1/appointments/{appt_id}/check-in", headers=provider_data["headers"])
    assert ci.status_code == 200
    assert ci.json()["status"] == "checked_in"

    co = await client.post(f"/api/v1/appointments/{appt_id}/complete", headers=provider_data["headers"])
    assert co.status_code == 200
    assert co.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_telehealth_checkin_goes_to_in_progress(client: AsyncClient, provider_data, patient_data):
    payload = appt_payload(
        provider_data["provider_id"], patient_data["patient_id"],
        "2026-09-01T15:00:00+00:00", "2026-09-01T15:30:00+00:00",
        appt_type="telehealth",
    )
    appt_id = (await client.post(
        "/api/v1/appointments", json=payload, headers=provider_data["headers"]
    )).json()["id"]

    ci = await client.post(f"/api/v1/appointments/{appt_id}/check-in", headers=provider_data["headers"])
    assert ci.status_code == 200
    assert ci.json()["status"] == "in_progress"
