"""
Security / OLAC tests for P0 fixes:
- Register never grants provider/admin role via request body
- Patient GET/PATCH access control
- Appointment GET/LIST scoping
- Prescription GET/LIST access control
- Provider availability admin-only write guard
"""
import pytest
from httpx import AsyncClient
from tests.conftest import _register_login


# ── Helpers ────────────────────────────────────────────────────────────

async def _mk_provider(client: AsyncClient, email: str) -> dict:
    admin_email = f"admin+{email}"
    admin_headers = await _register_login(client, admin_email, "admin", "Admin")
    res = await client.post("/api/v1/providers", json={
        "email": email, "password": "Password123!", "full_name": f"Dr {email}",
        "specialization": "General", "license_number": f"LIC-{email[:4]}",
        "consultation_fee": "100.00", "default_slot_minutes": 30,
    }, headers=admin_headers)
    assert res.status_code == 201, res.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return {"headers": headers, "provider_id": res.json()["id"]}


async def _mk_patient(client: AsyncClient, email: str) -> dict:
    headers = await _register_login(client, email, "patient", f"Pat {email}")
    res = await client.post("/api/v1/patients", json={
        "date_of_birth": "1990-01-01", "phone": "+1-555-0100",
    }, headers=headers)
    assert res.status_code == 201, res.text
    return {"headers": headers, "patient_id": res.json()["id"]}


async def _mk_appointment(client: AsyncClient, provider: dict, patient: dict, start: str, end: str) -> int:
    res = await client.post("/api/v1/appointments", json={
        "patient_id": patient["patient_id"],
        "provider_id": provider["provider_id"],
        "appointment_type": "in_person",
        "scheduled_start": start,
        "scheduled_end": end,
        "reason": "Check-up",
    }, headers=provider["headers"])
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ── Auth: register role hardlock ────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_ignores_role_field(client: AsyncClient):
    """Client-supplied role=admin must be silently ignored — user created as patient."""
    res = await client.post("/api/v1/auth/register", json={
        "email": "evil@swiftcare.io", "password": "Password123!", "full_name": "Evil",
        "role": "admin",
    })
    assert res.status_code == 201
    token = res.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["role"] == "patient"


# ── Patient OLAC ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_can_read_own_profile(client: AsyncClient):
    p = await _mk_patient(client, "self.read@swiftcare.io")
    res = await client.get(f"/api/v1/patients/{p['patient_id']}", headers=p["headers"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_patient_cannot_read_other_patient(client: AsyncClient):
    p1 = await _mk_patient(client, "p1.noread@swiftcare.io")
    p2 = await _mk_patient(client, "p2.noread@swiftcare.io")
    res = await client.get(f"/api/v1/patients/{p2['patient_id']}", headers=p1["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_provider_cannot_read_unrelated_patient(client: AsyncClient):
    prov = await _mk_provider(client, "dr.stranger@swiftcare.io")
    pat = await _mk_patient(client, "stranger.pat@swiftcare.io")
    res = await client.get(f"/api/v1/patients/{pat['patient_id']}", headers=prov["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_provider_can_read_assigned_patient(client: AsyncClient):
    prov = await _mk_provider(client, "dr.assign@swiftcare.io")
    pat = await _mk_patient(client, "assigned.pat@swiftcare.io")
    await _mk_appointment(client, prov, pat, "2027-01-10T09:00:00+00:00", "2027-01-10T09:30:00+00:00")
    res = await client.get(f"/api/v1/patients/{pat['patient_id']}", headers=prov["headers"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_patient_cannot_patch_other_patient(client: AsyncClient):
    p1 = await _mk_patient(client, "p1.nopatch@swiftcare.io")
    p2 = await _mk_patient(client, "p2.nopatch@swiftcare.io")
    res = await client.patch(
        f"/api/v1/patients/{p2['patient_id']}",
        json={"phone": "+1-000-0000"},
        headers=p1["headers"],
    )
    assert res.status_code == 403


# ── Appointment scoping ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_list_sees_only_own_appointments(client: AsyncClient):
    prov = await _mk_provider(client, "dr.scope@swiftcare.io")
    pat1 = await _mk_patient(client, "scope.pat1@swiftcare.io")
    pat2 = await _mk_patient(client, "scope.pat2@swiftcare.io")

    await _mk_appointment(client, prov, pat1, "2027-02-01T09:00:00+00:00", "2027-02-01T09:30:00+00:00")
    await _mk_appointment(client, prov, pat2, "2027-02-01T10:00:00+00:00", "2027-02-01T10:30:00+00:00")

    res = await client.get("/api/v1/appointments", headers=pat1["headers"])
    assert res.status_code == 200
    ids = [a["patient_id"] for a in res.json()]
    assert all(i == pat1["patient_id"] for i in ids)
    assert pat2["patient_id"] not in ids


@pytest.mark.asyncio
async def test_patient_cannot_get_other_patient_appointment(client: AsyncClient):
    prov = await _mk_provider(client, "dr.owncheck@swiftcare.io")
    pat1 = await _mk_patient(client, "own1@swiftcare.io")
    pat2 = await _mk_patient(client, "own2@swiftcare.io")
    appt_id = await _mk_appointment(client, prov, pat2, "2027-03-01T09:00:00+00:00", "2027-03-01T09:30:00+00:00")

    res = await client.get(f"/api/v1/appointments/{appt_id}", headers=pat1["headers"])
    assert res.status_code == 403


# ── Provider availability guard ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_cannot_write_other_provider_availability(client: AsyncClient):
    prov1 = await _mk_provider(client, "dr.prov1@swiftcare.io")
    prov2 = await _mk_provider(client, "dr.prov2@swiftcare.io")
    res = await client.post(
        f"/api/v1/providers/{prov2['provider_id']}/availability",
        json={"weekday": 0, "start_time": "09:00", "end_time": "17:00"},
        headers=prov1["headers"],
    )
    assert res.status_code == 403


# ── Prescription OLAC ───────────────────────────────────────────────────

async def _completed_appt_and_rx(client: AsyncClient, prov: dict, pat: dict, start: str, end: str) -> int:
    """Creates a completed appointment and a prescription. Returns rx_id."""
    appt_id = await _mk_appointment(client, prov, pat, start, end)
    await client.post(f"/api/v1/appointments/{appt_id}/check-in", headers=prov["headers"])
    await client.post(f"/api/v1/appointments/{appt_id}/complete", headers=prov["headers"])
    rx_res = await client.post("/api/v1/prescriptions", headers=prov["headers"], json={
        "appointment_id": appt_id,
        "patient_id": pat["patient_id"],
        "items": [{
            "drug_name": "Ibuprofen", "dosage_amount": "400", "dosage_unit": "mg",
            "frequency_per_day": 3, "duration_days": 5,
        }],
    })
    assert rx_res.status_code == 201, rx_res.text
    return rx_res.json()["id"]


@pytest.mark.asyncio
async def test_patient_can_get_own_prescription(client: AsyncClient):
    prov = await _mk_provider(client, "dr.rx.own@swiftcare.io")
    pat = await _mk_patient(client, "rx.own@swiftcare.io")
    rx_id = await _completed_appt_and_rx(client, prov, pat, "2027-04-01T09:00:00+00:00", "2027-04-01T09:30:00+00:00")
    res = await client.get(f"/api/v1/prescriptions/{rx_id}", headers=pat["headers"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_patient_cannot_get_other_patient_prescription(client: AsyncClient):
    prov = await _mk_provider(client, "dr.rx.cross@swiftcare.io")
    pat1 = await _mk_patient(client, "rx.cross1@swiftcare.io")
    pat2 = await _mk_patient(client, "rx.cross2@swiftcare.io")
    rx_id = await _completed_appt_and_rx(client, prov, pat1, "2027-04-02T09:00:00+00:00", "2027-04-02T09:30:00+00:00")
    res = await client.get(f"/api/v1/prescriptions/{rx_id}", headers=pat2["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_provider_can_get_own_prescription(client: AsyncClient):
    prov = await _mk_provider(client, "dr.rx.self@swiftcare.io")
    pat = await _mk_patient(client, "rx.self.pat@swiftcare.io")
    rx_id = await _completed_appt_and_rx(client, prov, pat, "2027-04-03T09:00:00+00:00", "2027-04-03T09:30:00+00:00")
    res = await client.get(f"/api/v1/prescriptions/{rx_id}", headers=prov["headers"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_provider_cannot_get_other_provider_prescription(client: AsyncClient):
    prov1 = await _mk_provider(client, "dr.rx.a@swiftcare.io")
    prov2 = await _mk_provider(client, "dr.rx.b@swiftcare.io")
    pat = await _mk_patient(client, "rx.shared.pat@swiftcare.io")
    rx_id = await _completed_appt_and_rx(client, prov1, pat, "2027-04-04T09:00:00+00:00", "2027-04-04T09:30:00+00:00")
    res = await client.get(f"/api/v1/prescriptions/{rx_id}", headers=prov2["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_prescriptions_list_patient_sees_only_own(client: AsyncClient):
    prov = await _mk_provider(client, "dr.rxlist@swiftcare.io")
    pat1 = await _mk_patient(client, "rxlist.p1@swiftcare.io")
    pat2 = await _mk_patient(client, "rxlist.p2@swiftcare.io")
    await _completed_appt_and_rx(client, prov, pat1, "2027-05-01T09:00:00+00:00", "2027-05-01T09:30:00+00:00")
    await _completed_appt_and_rx(client, prov, pat2, "2027-05-01T10:00:00+00:00", "2027-05-01T10:30:00+00:00")

    res = await client.get("/api/v1/prescriptions", headers=pat1["headers"])
    assert res.status_code == 200
    patient_ids = [r["patient_id"] for r in res.json()]
    assert all(pid == pat1["patient_id"] for pid in patient_ids)
    assert pat2["patient_id"] not in patient_ids


@pytest.mark.asyncio
async def test_provider_list_sees_only_own_appointments(client: AsyncClient):
    prov1 = await _mk_provider(client, "dr.provlist1@swiftcare.io")
    prov2 = await _mk_provider(client, "dr.provlist2@swiftcare.io")
    pat = await _mk_patient(client, "provlist.pat@swiftcare.io")
    await _mk_appointment(client, prov1, pat, "2027-06-01T09:00:00+00:00", "2027-06-01T09:30:00+00:00")
    await _mk_appointment(client, prov2, pat, "2027-06-01T10:00:00+00:00", "2027-06-01T10:30:00+00:00")

    res = await client.get("/api/v1/appointments", headers=prov1["headers"])
    assert res.status_code == 200
    provider_ids = [a["provider_id"] for a in res.json()]
    assert all(pid == prov1["provider_id"] for pid in provider_ids)
    assert prov2["provider_id"] not in provider_ids


# ── PATCH /providers/{id} authorization ────────────────────────────────

@pytest.mark.asyncio
async def test_provider_cannot_patch_other_provider_profile(client: AsyncClient):
    prov1 = await _mk_provider(client, "dr.patch.a@swiftcare.io")
    prov2 = await _mk_provider(client, "dr.patch.b@swiftcare.io")
    res = await client.patch(
        f"/api/v1/providers/{prov2['provider_id']}",
        json={"specialization": "Hacked"},
        headers=prov1["headers"],
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_patch_any_provider_profile(client: AsyncClient):
    prov = await _mk_provider(client, "dr.admin.target@swiftcare.io")
    admin_headers = await _register_login(client, "superadmin@swiftcare.io", "admin", "Super Admin")
    res = await client.patch(
        f"/api/v1/providers/{prov['provider_id']}",
        json={"specialization": "Pediatrics", "consultation_fee": "150.00"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["specialization"] == "Pediatrics"
