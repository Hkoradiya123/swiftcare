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


def _sub_key(conversation_id: str, user_id: int | None, agent: str) -> str:
    prefix = str(user_id) if user_id else "guest"
    return f"sub:{prefix}:{conversation_id}:{agent}"


async def load_history(conversation_id: str, user_id: int | None) -> list[dict]:
    data = await _get_redis().get(_key(conversation_id, user_id))
    return json.loads(data) if data else []


async def save_history(conversation_id: str, user_id: int | None, messages: list[dict]) -> None:
    await _get_redis().setex(_key(conversation_id, user_id), _HISTORY_TTL, json.dumps(messages))


async def load_sub_messages(conversation_id: str, user_id: int | None, agent: str) -> list:
    from langchain_core.messages import messages_from_dict
    data = await _get_redis().get(_sub_key(conversation_id, user_id, agent))
    if not data:
        return []
    return messages_from_dict(json.loads(data))


async def save_sub_messages(conversation_id: str, user_id: int | None, agent: str, messages: list) -> None:
    from langchain_core.messages import messages_to_dict
    # cap at 40 messages to avoid unbounded growth
    capped = messages[-40:]
    await _get_redis().setex(
        _sub_key(conversation_id, user_id, agent),
        _HISTORY_TTL,
        json.dumps(messages_to_dict(capped)),
    )


async def clear_sub_messages(conversation_id: str, user_id: int | None, agent: str) -> None:
    await _get_redis().delete(_sub_key(conversation_id, user_id, agent))


def _pending_key(conversation_id: str, user_id: int | None) -> str:
    prefix = str(user_id) if user_id else "guest"
    return f"pending:{prefix}:{conversation_id}"


async def save_pending_action(conversation_id: str, user_id: int | None, action: dict, ttl: int = 900) -> None:
    """Save a pending action (e.g. appointment booking) to Redis with 15 min TTL."""
    await _get_redis().setex(
        _pending_key(conversation_id, user_id),
        ttl,
        json.dumps(action),
    )


async def load_pending_action(conversation_id: str, user_id: int | None) -> dict | None:
    """Load a pending action from Redis."""
    data = await _get_redis().get(_pending_key(conversation_id, user_id))
    return json.loads(data) if data else None


async def clear_pending_action(conversation_id: str, user_id: int | None) -> None:
    """Clear a pending action from Redis."""
    await _get_redis().delete(_pending_key(conversation_id, user_id))


def new_conversation_id() -> str:
    return str(uuid.uuid4())
