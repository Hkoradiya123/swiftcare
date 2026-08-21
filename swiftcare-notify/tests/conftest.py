import pytest
import pytest_asyncio
import fakeredis.aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models  # register all models on RelayBase.metadata
from app.db.base import RelayBase


@pytest_asyncio.fixture
async def notify_engine():
    # Strip PostgreSQL schema prefix — SQLite has no schema concept
    for tbl in RelayBase.metadata.sorted_tables:
        tbl.schema = None

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(RelayBase.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(RelayBase.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(notify_engine):
    return async_sessionmaker(bind=notify_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def redis_client():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()
