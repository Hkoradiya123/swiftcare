import json
import logging
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.consumers.handlers import dispatch

logger = logging.getLogger(__name__)

STREAM = "swiftcare:events"
GROUP = "notify-group"


async def ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise


async def _mark_processed_if_new(session, event_id: str) -> bool:
    """
    Insert event_id using the PK constraint as the atomic guard.
    Returns True if already processed (duplicate), False if new.
    Works on SQLite (tests) and PostgreSQL (production) — no dialect-specific SQL.
    """
    from app.db.models import ProcessedEvent
    session.add(ProcessedEvent(event_id=event_id))
    try:
        await session.flush()
        return False
    except IntegrityError:
        await session.rollback()
        return True


async def handle_message(msg_id: bytes, fields: dict, redis: Redis, factory: async_sessionmaker) -> None:
    """
    Process one message. Public so tests can call it directly.
    XACK only on success — failed messages stay in the pending list for retry.
    """
    payload = json.loads(fields[b"data"])
    event_id = payload.get("event_id", "")
    logger.info("Received event event_id=%s type=%s", event_id, payload.get("event_type"))

    async with factory() as session:
        if await _mark_processed_if_new(session, event_id):
            logger.info("Skipping duplicate event %s", event_id)
            await redis.xack(STREAM, GROUP, msg_id)
            return

        try:
            await dispatch(payload, session)
            await session.commit()
            await redis.xack(STREAM, GROUP, msg_id)
            logger.info("Event processed and acked event_id=%s", event_id)
        except Exception:
            await session.rollback()
            logger.exception("Handler failed for event %s — leaving in pending list for retry", event_id)
            raise


async def run_consumer(redis: Redis, factory: async_sessionmaker, consumer_name: str = "notify-1") -> None:
    await ensure_group(redis)
    logger.info("Consumer %s started, listening on %s", consumer_name, STREAM)

    while True:
        resp = await redis.xreadgroup(GROUP, consumer_name, {STREAM: ">"}, count=10, block=5000)
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                try:
                    await handle_message(msg_id, fields, redis, factory)
                except Exception:
                    logger.exception("Unhandled error processing msg_id=%s — skipping", msg_id)
