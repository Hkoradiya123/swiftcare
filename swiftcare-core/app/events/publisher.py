import redis.asyncio as aioredis
from pydantic import BaseModel
from app.core.config import get_settings

STREAM = "swiftcare:events"


async def publish(event: BaseModel) -> None:
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url)
    try:
        await r.xadd(
            STREAM,
            {"data": event.model_dump_json()},
            maxlen=10_000,
            approximate=True,
        )
    finally:
        await r.aclose()
