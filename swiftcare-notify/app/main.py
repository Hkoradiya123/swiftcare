import asyncio
import logging
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.db.engine import AsyncSessionLocal
from app.consumers.runner import run_consumer
from app.storage.s3 import ensure_bucket, get_s3_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    redis = aioredis.from_url(settings.redis_url)
    try:
        await run_consumer(redis, AsyncSessionLocal, consumer_name=settings.consumer_name)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    settings = get_settings()
    ensure_bucket(get_s3_client(), settings.s3_bucket)
    asyncio.run(main())
