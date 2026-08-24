import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


async def _completed_appointment(client: AsyncClient, provider_data: dict, patient_data: dict) -> int:
    """Creates and completes an appointment. Returns appointment_id."""
    appt_res = await client.post("/api/v1/appointments", headers=provider_data["headers"], json={
        "patient_id": patient_data["patient_id"],
        "provider_id": provider_data["provider_id"],
        "appointment_type": "in_person",
        "scheduled_start": "2026-10-01T10:00:00+00:00",
        "scheduled_end": "2026-10-01T10:30:00+00:00",
        "reason": "Checkup",
    })
    assert appt_res.status_code == 201, appt_res.text
    appt_id = appt_res.json()["id"]

    await client.post(f"/api/v1/appointments/{appt_id}/check-in", headers=provider_data["headers"])
    co = await client.post(f"/api/v1/appointments/{appt_id}/complete", headers=provider_data["headers"])
    assert co.json()["status"] == "completed"
    return appt_id


def _rx_payload(appointment_id: int, patient_id: int) -> dict:
    return {
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "items": [{
            "drug_name": "Amoxicillin",
            "dosage_amount": "500",
            "dosage_unit": "mg",
            "frequency_per_day": 3,
            "duration_days": 7,
        }],
    }


@pytest.mark.asyncio
async def test_create_prescription_success(client: AsyncClient, provider_data, patient_data):
    appt_id = await _completed_appointment(client, provider_data, patient_data)
    res = await client.post("/api/v1/prescriptions",
                            json=_rx_payload(appt_id, patient_data["patient_id"]),
                            headers=provider_data["headers"])
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "active"
    assert len(data["items"]) == 1
    assert data["items"][0]["drug_name"] == "Amoxicillin"


@pytest.mark.asyncio
async def test_allergy_blocks_prescription_returns_409(client: AsyncClient, provider_data, patient_data):
    # Record drug allergy first
    allergy_res = await client.post("/api/v1/allergies", headers=provider_data["headers"], json={
        "patient_id": patient_data["patient_id"],
        "allergen": "Amoxicillin",
        "allergy_type": "drug",
        "severity": "severe",
    })
    assert allergy_res.status_code == 201, allergy_res.text

    appt_id = await _completed_appointment(client, provider_data, patient_data)
    res = await client.post("/api/v1/prescriptions",
                            json=_rx_payload(appt_id, patient_data["patient_id"]),
                            headers=provider_data["headers"])
    assert res.status_code == 409
    assert "amoxicillin" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_prescription_on_incomplete_appointment_returns_400(client: AsyncClient, provider_data, patient_data):
    # Appointment exists but is not completed
    appt_res = await client.post("/api/v1/appointments", headers=provider_data["headers"], json={
        "patient_id": patient_data["patient_id"],
        "provider_id": provider_data["provider_id"],
        "appointment_type": "in_person",
        "scheduled_start": "2026-10-02T10:00:00+00:00",
        "scheduled_end": "2026-10-02T10:30:00+00:00",
        "reason": "Checkup",
    })
    appt_id = appt_res.json()["id"]

    res = await client.post("/api/v1/prescriptions",
                            json=_rx_payload(appt_id, patient_data["patient_id"]),
                            headers=provider_data["headers"])
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_patient_cannot_create_prescription_returns_403(client: AsyncClient, provider_data, patient_data):
    appt_id = await _completed_appointment(client, provider_data, patient_data)
    res = await client.post("/api/v1/prescriptions",
                            json=_rx_payload(appt_id, patient_data["patient_id"]),
                            headers=patient_data["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client: AsyncClient, provider_data, patient_data):
    """
    Fires 11 real INCR calls against FakeRedis — verifies the window actually
    blocks on the 11th call, not just that the code path exists.
    """
    appt_id = await _completed_appointment(client, provider_data, patient_data)
    payload = _rx_payload(appt_id, patient_data["patient_id"])

    # First 10 should pass (or fail for business reasons, not rate limit)
    for _ in range(10):
        res = await client.post("/api/v1/prescriptions", json=payload, headers=provider_data["headers"])
        assert res.status_code != 429, f"Hit rate limit early: {res.json()}"

    # 11th must be blocked
    res = await client.post("/api/v1/prescriptions", json=payload, headers=provider_data["headers"])
    assert res.status_code == 429
    assert "Rate limit" in res.json()["detail"]
