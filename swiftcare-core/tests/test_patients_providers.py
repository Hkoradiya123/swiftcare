import pytest
from httpx import AsyncClient
from tests.conftest import _register_login


async def get_authenticated_headers(client: AsyncClient, email: str, role: str) -> dict:
    """Helper to register and login a user and return Auth header."""
    reg_payload = {
        "email": email,
        "password": "Password123!",
        "full_name": f"User {role}",
        "role": role,
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    token = reg_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_patient_crud_flow(client: AsyncClient):
    # 1. Register Patient User
    headers = await get_authenticated_headers(client, "patient1@swiftcare.io", "patient")

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

    # 4. Update Profile
    update_payload = {"phone": "+1-555-9999", "address": "456 Updated St"}
    update_res = await client.patch(f"/api/v1/patients/{patient_id}", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["phone"] == "+1-555-9999"


@pytest.mark.asyncio
async def test_provider_crud_and_availability_flow(client: AsyncClient):
    # 1. Admin onboards provider in one shot
    admin_headers = await _register_login(client, "admin.smith@swiftcare.io", "admin", "Admin")
    create_res = await client.post("/api/v1/providers", json={
        "email": "dr.smith@swiftcare.io", "password": "Password123!", "full_name": "User provider",
        "specialization": "Cardiology", "license_number": "CARD-99182",
        "consultation_fee": "250.00", "default_slot_minutes": 30,
    }, headers=admin_headers)
    assert create_res.status_code == 201
    prov_data = create_res.json()
    provider_id = prov_data["id"]
    assert prov_data["specialization"] == "Cardiology"
    login = await client.post("/api/v1/auth/login", json={"email": "dr.smith@swiftcare.io", "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # 3. Admin adds Availability Slot for provider via /{provider_id}/availability
    avail_payload = {
        "weekday": 0,  # Monday
        "start_time": "09:00",
        "end_time": "17:00"
    }
    avail_res = await client.post(f"/api/v1/providers/{provider_id}/availability", json=avail_payload, headers=admin_headers)
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
    admin_headers = await _register_login(client, "admin.update@swiftcare.io", "admin", "Admin")
    await client.post("/api/v1/providers", json={
        "email": "dr.update@swiftcare.io", "password": "Password123!", "full_name": "Dr Update",
        "specialization": "Neurology", "license_number": "NEURO-001",
        "consultation_fee": "300.00", "default_slot_minutes": 30,
    }, headers=admin_headers)
    login = await client.post("/api/v1/auth/login", json={"email": "dr.update@swiftcare.io", "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

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
