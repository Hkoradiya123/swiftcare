import asyncio
import logging
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.db.engine import AsyncSessionLocal
from app.consumers.runner import run_consumer
from app.storage.s3 import ensure_bucket, get_s3_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

REMINDER_INTERVAL = 300  # 5 minutes, same cadence as Celery beat schedule


async def init_db() -> None:
    from sqlalchemy import text
    from app.db.engine import engine
    from app.db.base import RelayBase
    import app.db.models  # noqa: F401 — register all models
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS relay"))
        await conn.run_sync(RelayBase.metadata.create_all)
    logger.info("DB schema ready")


async def reminder_loop() -> None:
    from app.tasks.reminders import _send_reminders_async
    while True:
        try:
            await _send_reminders_async(AsyncSessionLocal)
        except Exception:
            logger.exception("Reminder run failed")
        await asyncio.sleep(REMINDER_INTERVAL)


async def main() -> None:
    await init_db()
    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url)
    asyncio.create_task(reminder_loop())
    logger.info("Reminder loop started (every %ds)", REMINDER_INTERVAL)
    try:
        await run_consumer(redis, AsyncSessionLocal, consumer_name=settings.consumer_name)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    settings = get_settings()
    try:
        ensure_bucket(get_s3_client(), settings.s3_bucket)
    except Exception as e:
        logger.warning("S3 unavailable at startup — PDF uploads will fail: %s", e)
    asyncio.run(main())
