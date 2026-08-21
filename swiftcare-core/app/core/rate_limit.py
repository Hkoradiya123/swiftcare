from fastapi import Depends, HTTPException, status
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.models.user import User
import redis.asyncio as aioredis


def rate_limit(max_calls: int, window_seconds: int):
    """Fixed-window rate limiter. Key per user+route."""
    async def _check(current_user: User = Depends(get_current_user)):
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url)
        key = f"rl:{current_user.id}:{max_calls}:{window_seconds}"
        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window_seconds)
            if count > max_calls:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {max_calls} requests per {window_seconds}s.",
                )
        finally:
            await r.aclose()
    return _check
