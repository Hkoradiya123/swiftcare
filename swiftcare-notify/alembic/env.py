import os
from logging.config import fileConfig
from dotenv import load_dotenv
from sqlalchemy import pool, text
from alembic import context

load_dotenv()

from app.db.base import RelayBase
import app.db.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = RelayBase.metadata

db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
config.set_main_option("sqlalchemy.url", db_url)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == "relay"
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema="relay",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    async_url = os.getenv("DATABASE_URL", "")
    connectable = create_async_engine(async_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS relay"))
        await connection.commit()
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn,
                target_metadata=target_metadata,
                include_schemas=True,
                include_name=include_name,
                version_table_schema="relay",
            )
        )
        async with connection.begin():
            await connection.run_sync(lambda conn: context.run_migrations())

    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
