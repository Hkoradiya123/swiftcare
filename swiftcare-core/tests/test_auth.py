import pytest
from httpx import AsyncClient
from tests.conftest import _register_login


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    payload = {
        "email": "dr.sharma@swiftcare.io",
        "password": "SecretPassword123!",
        "full_name": "Dr Sharma",
        "role": "provider"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient):
    payload = {
        "email": "patient.doe@swiftcare.io",
        "password": "SecretPassword123!",
        "full_name": "John Doe",
        "role": "patient"
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert res2.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_login_success_and_me_endpoint(client: AsyncClient):
    headers = await _register_login(client, "admin@swiftcare.io", "admin", "System Admin")
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "admin@swiftcare.io"
    assert me_data["full_name"] == "System Admin"
    assert me_data["role"] == "admin"
    assert me_data["is_active"] is True


@pytest.mark.asyncio
async def test_login_invalid_password_returns_401(client: AsyncClient):
    # Register user
    reg_payload = {
        "email": "test@swiftcare.io",
        "password": "CorrectPassword123!",
        "full_name": "Test User",
        "role": "patient"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Login with wrong password
    login_payload = {
        "email": "test@swiftcare.io",
        "password": "WrongPassword123!"
    }
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 401
    assert login_res.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_short_password_returns_422(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "short@swiftcare.io", "password": "abc", "full_name": "Test", "role": "patient",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_blank_name_returns_422(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "blank@swiftcare.io", "password": "Password123!", "full_name": "   ", "role": "patient",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patient_on_provider_route_returns_403(client: AsyncClient):
    headers = await _register_login(client, "pat.role@swiftcare.io", "patient", "Pat Role")
    res = await client.post("/api/v1/providers", json={
        "specialization": "Surgery", "license_number": "LIC-X",
        "consultation_fee": "200.00", "default_slot_minutes": 30,
    }, headers=headers)
    assert res.status_code == 403
