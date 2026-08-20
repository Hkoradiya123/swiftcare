import json
import redis.asyncio as aioredis
from app.core.config import get_settings


async def publish(stream: str, payload: dict) -> None:
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url)
    try:
        await r.xadd(stream, {"data": json.dumps(payload)})
    finally:
        await r.aclose()
