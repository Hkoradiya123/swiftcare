import pytest
from httpx import AsyncClient


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
    # 1. Register Provider User
    headers = await get_authenticated_headers(client, "dr.smith@swiftcare.io", "provider")

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

    # 3. Add Availability Slot
    avail_payload = {
        "weekday": 0,  # Monday
        "start_time": "09:00",
        "end_time": "17:00"
    }
    avail_res = await client.post(f"/api/v1/providers/{provider_id}/availability", json=avail_payload, headers=headers)
    assert avail_res.status_code == 201
    assert avail_res.json()["start_time"] == "09:00:00"

    # 4. List Providers with Specialization Filter
    list_res = await client.get("/api/v1/providers?specialization=cardio", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["license_number"] == "CARD-99182"

    # 5. Overlapping availability slot returns 409 Conflict
    overlap_payload = {
        "weekday": 0,  # Monday
        "start_time": "11:00",
        "end_time": "15:00"
    }
    overlap_res = await client.post(f"/api/v1/providers/{provider_id}/availability", json=overlap_payload, headers=headers)
    assert overlap_res.status_code == 409

    # 6. List Availabilities (GET)
    avail_list_res = await client.get(f"/api/v1/providers/{provider_id}/availability", headers=headers)
    assert avail_list_res.status_code == 200
    slots = avail_list_res.json()
    assert len(slots) == 1
    slot_id = slots[0]["id"]

    # 7. Update Availability Slot (PATCH)
    patch_res = await client.patch(f"/api/v1/providers/{provider_id}/availability/{slot_id}", json={"start_time": "10:00"}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["start_time"] == "10:00:00"

    # 8. Delete Availability Slot (DELETE)
    del_res = await client.delete(f"/api/v1/providers/{provider_id}/availability/{slot_id}", headers=headers)
    assert del_res.status_code == 204

    # 9. Bulk Create Availability Slots
    bulk_payload = [
        {"weekday": 1, "start_time": "09:00", "end_time": "13:00"},
        {"weekday": 1, "start_time": "15:00", "end_time": "19:00"}
    ]
    bulk_res = await client.post(f"/api/v1/providers/{provider_id}/availability/bulk", json=bulk_payload, headers=headers)
    assert bulk_res.status_code == 201
    assert len(bulk_res.json()) == 2





@pytest.mark.asyncio
async def test_patient_scoping_by_role(client: AsyncClient):
    # 1. Admin header
    admin_headers = await get_authenticated_headers(client, "admin1@swiftcare.io", "admin")

    # 2. Admin listing returns all patients
    res = await client.get("/api/v1/patients", headers=admin_headers)
    assert res.status_code == 200
    assert "items" in res.json()

