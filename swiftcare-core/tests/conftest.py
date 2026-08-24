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


class _PipelineMock:
    def __init__(self, stub):
        self._stub = stub
        self._cmds = []

    def get(self, key: str):
        self._cmds.append(("get", key))
        return self

    def incr(self, key: str):
        self._cmds.append(("incr", key))
        return self

    def expire(self, key: str, ttl: int):
        self._cmds.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for cmd in self._cmds:
            op = cmd[0]
            if op == "get":
                val = self._stub._counters.get(cmd[1], 0)
                results.append(str(val) if val else None)
            elif op == "incr":
                self._stub._counters[cmd[1]] += 1
                results.append(self._stub._counters[cmd[1]])
            elif op == "expire":
                results.append(True)
        self._cmds = []
        return results


class _CountingRedis:
    """
    Minimal Redis stub with real INCR accumulation semantics.
    A plain AsyncMock(return_value=1) would make the 429 test pass even if
    the rate limiter logic were completely broken. This actually counts.
    """
    def __init__(self):
        self._counters: dict = defaultdict(int)

    def pipeline(self):
        return _PipelineMock(self)

    async def get(self, key: str):
        val = self._counters.get(key, 0)
        return str(val) if val else None

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
    from sqlalchemy import update
    from app.models.user import User
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "full_name": full_name,
    })
    assert res.status_code == 201, res.text
    if role != "patient":
        async with TestingSessionLocal() as session:
            await session.execute(update(User).where(User.email == email).values(role=role))
            await session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest_asyncio.fixture
async def provider_data(client: AsyncClient):
    admin_headers = await _register_login(client, "admin.fixture@swiftcare.io", "admin", "Admin User")
    res = await client.post("/api/v1/providers", json={
        "email": "dr.test@swiftcare.io", "password": "Password123!", "full_name": "Dr Test",
        "specialization": "General", "license_number": "LIC-001",
        "consultation_fee": "100.00", "default_slot_minutes": 30,
    }, headers=admin_headers)
    assert res.status_code == 201, res.text
    provider_id = res.json()["id"]
    login = await client.post("/api/v1/auth/login", json={"email": "dr.test@swiftcare.io", "password": "Password123!"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return {"headers": headers, "provider_id": provider_id}


@pytest_asyncio.fixture
async def patient_data(client: AsyncClient):
    headers = await _register_login(client, "patient.test@swiftcare.io", "patient", "Pat Test")
    res = await client.post("/api/v1/patients", json={
        "date_of_birth": "1990-01-01", "phone": "+1-555-0100",
    }, headers=headers)
    assert res.status_code == 201, res.text
    return {"headers": headers, "patient_id": res.json()["id"]}
