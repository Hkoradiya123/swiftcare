import math
import time
from typing import Dict, Optional
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.models.user import User


class DualLayerRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Dual-layer Sliding Window Counter (Hybrid) rate limiter middleware.
    Layer 1: Global server-wide capacity protection.
    Layer 2: Per-client (User ID or Client IP) / per-path rate limits.
    """
    def __init__(
        self,
        app,
        global_max_calls: int = 5000,
        client_max_calls: int = 60,
        window_seconds: int = 60,
        path_limits: Optional[Dict[str, int]] = None,
    ):
        super().__init__(app)
        self.global_max_calls = global_max_calls
        self.client_max_calls = client_max_calls
        self.window_seconds = window_seconds
        self.path_limits = path_limits or {
            "/health": 500,
            "/docs": 200,
            "/redoc": 200,
            "/openapi.json": 200,
            "/": 100,
        }
        self.settings = get_settings()

    def _get_client_identifier(self, request: Request) -> str:
        """Identifies requester by User ID (from JWT) or Client IP."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(
                    token,
                    self.settings.secret_key,
                    algorithms=[self.settings.algorithm]
                )
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
            except JWTError:
                pass

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        client_max = self.path_limits.get(path, self.client_max_calls)
        client_id = self._get_client_identifier(request)

        now = time.time()
        curr_window = int(now // self.window_seconds)
        prev_window = curr_window - 1
        time_elapsed_pct = (now % self.window_seconds) / self.window_seconds
        retry_after = math.ceil(self.window_seconds * (1.0 - time_elapsed_pct))

        global_curr = f"rl:global:{curr_window}:{self.window_seconds}"
        global_prev = f"rl:global:{prev_window}:{self.window_seconds}"

        client_curr = f"rl:{client_id}:{path}:{curr_window}:{self.window_seconds}"
        client_prev = f"rl:{client_id}:{path}:{prev_window}:{self.window_seconds}"

        r = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        try:
            pipe = r.pipeline()
            # 1. Global server counter
            pipe.get(global_prev)
            pipe.incr(global_curr)
            pipe.expire(global_curr, self.window_seconds * 2)
            # 2. Individual client counter
            pipe.get(client_prev)
            pipe.incr(client_curr)
            pipe.expire(client_curr, self.window_seconds * 2)

            g_prev, g_curr, _, c_prev, c_curr, _ = await pipe.execute()

            # Global Limit check
            g_prev_count = int(g_prev) if g_prev else 0
            g_estimated = (g_prev_count * (1.0 - time_elapsed_pct)) + int(g_curr)
            if g_estimated > self.global_max_calls:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Server is experiencing high traffic. Please retry shortly.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            # Client Limit check
            c_prev_count = int(c_prev) if c_prev else 0
            c_estimated = (c_prev_count * (1.0 - time_elapsed_pct)) + int(c_curr)
            remaining = max(0, int(client_max - c_estimated))

            if c_estimated > client_max:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded on {path}. Max {client_max} requests per {self.window_seconds}s.",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(client_max),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(client_max)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response
        except Exception:
            return await call_next(request)
        finally:
            await r.aclose()


def rate_limit(max_calls: int, window_seconds: int):
    """
    Sliding-window counter (hybrid) route-level rate limiter.
    Keyed per authenticated user + window.
    """
    async def _check(current_user: User = Depends(get_current_user)):
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)

        now = time.time()
        curr_window = int(now // window_seconds)
        prev_window = curr_window - 1
        time_elapsed_pct = (now % window_seconds) / window_seconds

        curr_key = f"rl:{current_user.id}:{max_calls}:{window_seconds}:{curr_window}"
        prev_key = f"rl:{current_user.id}:{max_calls}:{window_seconds}:{prev_window}"

        try:
            pipe = r.pipeline()
            pipe.get(prev_key)
            pipe.incr(curr_key)
            pipe.expire(curr_key, window_seconds * 2)
            prev_val, curr_count, _ = await pipe.execute()

            prev_count = int(prev_val) if prev_val else 0
            estimated_count = (prev_count * (1.0 - time_elapsed_pct)) + int(curr_count)

            if estimated_count > max_calls:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {max_calls} requests per {window_seconds}s.",
                )
        finally:
            await r.aclose()

    return _check
