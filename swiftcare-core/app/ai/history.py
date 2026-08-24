import json
import uuid
from redis.asyncio import Redis
from app.core.config import get_settings

_HISTORY_TTL = 7200  # 2 hours
_pool: Redis | None = None


def _get_redis() -> Redis:
    global _pool
    if _pool is None:
        _pool = Redis.from_url(get_settings().redis_url, decode_responses=True, max_connections=20)
    return _pool


def _key(conversation_id: str, user_id: int | None) -> str:
    # namespace by user so one user cannot read another's conversation history (IDOR fix)
    prefix = str(user_id) if user_id else "guest"
    return f"chat:{prefix}:{conversation_id}"


async def load_history(conversation_id: str, user_id: int | None) -> list[dict]:
    data = await _get_redis().get(_key(conversation_id, user_id))
    return json.loads(data) if data else []


async def save_history(conversation_id: str, user_id: int | None, messages: list[dict]) -> None:
    await _get_redis().setex(_key(conversation_id, user_id), _HISTORY_TTL, json.dumps(messages))


def new_conversation_id() -> str:
    return str(uuid.uuid4())
