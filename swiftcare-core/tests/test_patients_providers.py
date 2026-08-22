import pytest
from httpx import AsyncClient
from tests.conftest import _register_login


@pytest.mark.asyncio
async def test_patient_crud_flow(client: AsyncClient):
    # 1. Register Patient User
    headers = await _register_login(client, "patient1@swiftcare.io", "patient", "User patient")

    # 2. Create Patient Profile
    create_payload = {
        "date_of_birth": "1995-05-15",
        "phone": "+1-555-0199",
        "blood_group": "O+",
        "address": "123 Healthcare Ave"
    }
    create_res = await client.post("/api/v1/patients", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    patient_data = create_res.json()
    patient_id = patient_data["id"]
    assert patient_data["phone"] == "+1-555-0199"
    assert patient_data["email"] == "patient1@swiftcare.io"

    # 3. Duplicate profile fails
    dup_res = await client.post("/api/v1/patients", json=create_payload, headers=headers)
    assert dup_res.status_code == 409

    # 4. Update Profile (patient updates their own)
    update_payload = {"phone": "+1-555-9999", "address": "456 Updated St"}
    update_res = await client.patch(f"/api/v1/patients/{patient_id}", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["phone"] == "+1-555-9999"


@pytest.mark.asyncio
async def test_provider_crud_and_availability_flow(client: AsyncClient):
    # 1. Register Provider User (role patched in DB)
    headers = await _register_login(client, "dr.smith@swiftcare.io", "provider", "User provider")

    # 2. Create Provider Profile
    provider_payload = {
        "specialization": "Cardiology",
        "license_number": "CARD-99182",
        "consultation_fee": "250.00",
        "default_slot_minutes": 30
    }
    create_res = await client.post("/api/v1/providers", json=provider_payload, headers=headers)
    assert create_res.status_code == 201
    prov_data = create_res.json()
    provider_id = prov_data["id"]
    assert prov_data["specialization"] == "Cardiology"

    # 3. Add Availability Slot via /me (provider self-management)
    avail_payload = {"weekday": 0, "start_time": "09:00", "end_time": "17:00"}
    avail_res = await client.post("/api/v1/providers/me/availability", json=avail_payload, headers=headers)
    assert avail_res.status_code == 201
    assert avail_res.json()["start_time"] == "09:00:00"

    # 4. List Providers with Specialization Filter
    list_res = await client.get("/api/v1/providers?specialization=cardio", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["license_number"] == "CARD-99182"

    # 5. Overlapping availability slot returns 409 Conflict
    overlap_payload = {"weekday": 0, "start_time": "11:00", "end_time": "15:00"}
    overlap_res = await client.post("/api/v1/providers/me/availability", json=overlap_payload, headers=headers)
    assert overlap_res.status_code == 409

    # 6. List Availabilities via /me
    avail_list_res = await client.get("/api/v1/providers/me/availability", headers=headers)
    assert avail_list_res.status_code == 200
    slots = avail_list_res.json()
    assert len(slots) == 1
    slot_id = slots[0]["id"]

    # 7. Update Availability Slot via /me
    patch_res = await client.patch(
        f"/api/v1/providers/me/availability/{slot_id}",
        json={"start_time": "10:00"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["start_time"] == "10:00:00"

    # 8. Delete Availability Slot via /me
    del_res = await client.delete(f"/api/v1/providers/me/availability/{slot_id}", headers=headers)
    assert del_res.status_code == 204

    # 9. Bulk Create Availability Slots via Array Payload on POST /me/availability
    bulk_payload = [
        {"weekday": 1, "start_time": "09:00", "end_time": "13:00"},
        {"weekday": 1, "start_time": "15:00", "end_time": "19:00"}
    ]
    bulk_res = await client.post("/api/v1/providers/me/availability", json=bulk_payload, headers=headers)
    assert bulk_res.status_code == 201
    assert len(bulk_res.json()) == 2

    # 10. Provider cannot POST to /{provider_id}/availability (admin-only)
    blocked = await client.post(
        f"/api/v1/providers/{provider_id}/availability",
        json=avail_payload,
        headers=headers,
    )
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_provider_update_own_profile(client: AsyncClient):
    headers = await _register_login(client, "dr.update@swiftcare.io", "provider", "Dr Update")
    await client.post("/api/v1/providers", json={
        "specialization": "Neurology", "license_number": "NEURO-001",
        "consultation_fee": "300.00", "default_slot_minutes": 30,
    }, headers=headers)

    patch_res = await client.patch("/api/v1/providers/me", json={
        "specialization": "Pediatrics", "consultation_fee": "200.00",
    }, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["specialization"] == "Pediatrics"
    assert patch_res.json()["consultation_fee"] == "200.00"


@pytest.mark.asyncio
async def test_patient_scoping_by_role(client: AsyncClient):
    # Admin listing returns all patients
    admin_headers = await _register_login(client, "admin1@swiftcare.io", "admin", "Admin User")
    res = await client.get("/api/v1/patients", headers=admin_headers)
    assert res.status_code == 200
    assert "items" in res.json()
