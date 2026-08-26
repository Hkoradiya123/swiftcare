import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import redis.asyncio as aioredis

# Load .env file from root
root_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(root_env)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def test_redis():
    print("=" * 50)
    print("🚀 Testing Redis Connection...")
    safe_url = REDIS_URL
    if "@" in safe_url:
        proto, rest = safe_url.split("://", 1)
        creds, host = rest.split("@", 1)
        safe_url = f"{proto}://***:***@{host}"
    print(f"📍 Target URL: {safe_url}")
    print("=" * 50)

    try:
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        print(f"❌ Failed to parse Redis URL: {e}")
        return

    # 1. Ping Test
    try:
        print("\n1️⃣  Testing PING...")
        pong = await r.ping()
        print(f"   ✅ PING Success! Response: {pong}")
    except Exception as e:
        print(f"   ❌ PING Failed: {e}")
        await r.aclose()
        return

    # 2. Pipeline Test (Rate Limiter check)
    try:
        print("\n2️⃣  Testing Pipelines (Used by Rate Limiter)...")
        pipe = r.pipeline()
        pipe.incr("test:rate_limit:counter")
        pipe.expire("test:rate_limit:counter", 10)
        results = await pipe.execute()
        print(f"   ✅ Pipeline Success! Counter: {results[0]}")
    except Exception as e:
        print(f"   ❌ Pipeline Failed: {e}")

    # 3. Redis Streams Test (Used by Events & Notify Service)
    stream_name = "test:swiftcare:stream"
    group_name = "test:notify_group"
    try:
        print("\n3️⃣  Testing Redis Streams (XADD, XGROUP, XREADGROUP, XACK)...")

        # Create consumer group
        try:
            await r.xgroup_create(stream_name, group_name, id="0", mkstream=True)
            print("   ✅ Stream Group Created.")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                print("   ℹ️  Stream Group already exists (OK).")
            else:
                raise e

        # Publish test event
        msg_id = await r.xadd(stream_name, {"event": "test_event", "status": "ok"})
        print(f"   ✅ Published message (XADD) with ID: {msg_id}")

        # Read message via consumer group
        resp = await r.xreadgroup(group_name, "test_consumer_1", {stream_name: ">"}, count=1, block=2000)
        if resp and resp[0][1]:
            read_msg_id, fields = resp[0][1][0]
            print(f"   ✅ Received message (XREADGROUP): {fields}")
            # Ack message
            await r.xack(stream_name, group_name, read_msg_id)
            print(f"   ✅ Acknowledged message (XACK).")
        else:
            print("   ⚠️  No message received in stream.")

    except Exception as e:
        print(f"   ❌ Redis Stream Test Failed: {e}")

    # Clean up test keys
    try:
        await r.delete("test:rate_limit:counter", stream_name)
    except Exception:
        pass

    await r.aclose()
    print("\n" + "=" * 50)
    print("🎉 All Tests Finished!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_redis())
