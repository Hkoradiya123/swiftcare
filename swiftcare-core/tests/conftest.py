import sys
from pathlib import Path

# Add swiftcare-contracts to sys.path
contracts_dir = str(Path(__file__).resolve().parents[2] / "swiftcare-contracts")
if contracts_dir not in sys.path:
    sys.path.insert(0, contracts_dir)

from sqlalchemy import update

import pytest
import pytest_asyncio
from collections import defaultdict
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


import app.models  # Register all ORM models on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class _CountingRedis:
    """
    Minimal Redis stub with real INCR accumulation semantics.
    A plain AsyncMock(return_value=1) would make the 429 test pass even if
    the rate limiter logic were completely broken. This actually counts.
    """
    def __init__(self):
        self._counters: dict = defaultdict(int)

    async def incr(self, key: str) -> int:
        self._counters[key] += 1
        return self._counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        pass  # TTL not needed in synchronous tests

    async def xadd(self, *a, **kw) -> None:
        pass

    async def aclose(self) -> None:
        pass


@pytest_asyncio.fixture(autouse=True)
async def mock_redis():
    """
    Per-test _CountingRedis for rate limiter — counters reset each test so
    keys never leak between runs. Publisher stays AsyncMock (relay not built yet).
    """
    counter = _CountingRedis()
    publisher_mock = AsyncMock()
    publisher_mock.xadd = AsyncMock()
    publisher_mock.aclose = AsyncMock()
    # patch the module-level name, not the shared redis.asyncio.from_url attribute
    with patch("app.core.rate_limit.aioredis", new=MagicMock(from_url=lambda _: counter)), \
         patch("app.events.publisher.aioredis", new=MagicMock(from_url=lambda _: publisher_mock)):
        yield counter


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Shared scenario helpers ────────────────────────────────────────────

async def _register_login(client: AsyncClient, email: str, role: str, full_name: str) -> dict:
    """Register a user (always PATIENT) then patch role in DB if needed."""
    from app.models.user import User as UserModel
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "full_name": full_name,
    })
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]

    if role != "patient":
        async with TestingSessionLocal() as session:
            await session.execute(
                update(UserModel).where(UserModel.email == email).values(role=role)
            )
            await session.commit()

    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def provider_data(client: AsyncClient):
    headers = await _register_login(client, "dr.test@swiftcare.io", "provider", "Dr Test")
    res = await client.post("/api/v1/providers", json={
        "specialization": "General", "license_number": "LIC-001",
        "consultation_fee": "100.00", "default_slot_minutes": 30,
    }, headers=headers)
    assert res.status_code == 201, res.text
    return {"headers": headers, "provider_id": res.json()["id"]}


@pytest_asyncio.fixture
async def patient_data(client: AsyncClient):
    headers = await _register_login(client, "patient.test@swiftcare.io", "patient", "Pat Test")
    res = await client.post("/api/v1/patients", json={
        "date_of_birth": "1990-01-01", "phone": "+1-555-0100",
    }, headers=headers)
    assert res.status_code == 201, res.text
    return {"headers": headers, "patient_id": res.json()["id"]}
