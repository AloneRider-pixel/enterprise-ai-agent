"""
Redis client for caching, conversation memory, and rate limiting.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client with caching and rate limiting support."""

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection."""
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await self.client.ping()
        logger.info("Redis connection established")

    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()

    # ─── Caching ───

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if not found or expired."""
        if not self.client:
            return None
        try:
            value = await self.client.get(f"cache:{key}")
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Redis cache get error: {e}")
            return None

    async def cache_set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL (default 1 hour)."""
        if not self.client:
            return
        try:
            await self.client.setex(
                f"cache:{key}",
                ttl,
                json.dumps(value, default=str),
            )
        except Exception as e:
            logger.warning(f"Redis cache set error: {e}")

    async def cache_delete(self, key: str):
        """Delete a cached value."""
        if not self.client:
            return
        try:
            await self.client.delete(f"cache:{key}")
        except Exception as e:
            logger.warning(f"Redis cache delete error: {e}")

    # ─── Conversation Memory ───

    async def store_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
        max_messages: int = 20,
    ):
        """Store a chat message in session memory (sliding window)."""
        if not self.client:
            return
        try:
            key = f"session:{session_id}:messages"
            message = {
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "timestamp": time.time(),
            }
            pipe = self.client.pipeline()
            pipe.rpush(key, json.dumps(message, default=str))
            # Keep only last N messages (sliding window)
            pipe.ltrim(key, -max_messages, -1)
            pipe.expire(key, 86400)  # 24 hour expiry
            await pipe.execute()
        except Exception as e:
            logger.warning(f"Redis store message error: {e}")

    async def get_messages(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Get recent messages from session memory."""
        if not self.client:
            return []
        try:
            key = f"session:{session_id}:messages"
            raw_messages = await self.client.lrange(key, -limit, -1)
            messages = []
            for raw in raw_messages:
                try:
                    messages.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
            return messages
        except Exception as e:
            logger.warning(f"Redis get messages error: {e}")
            return []

    async def clear_session(self, session_id: str):
        """Clear all data for a session."""
        if not self.client:
            return
        try:
            keys = await self.client.keys(f"session:{session_id}:*")
            if keys:
                await self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis clear session error: {e}")

    # ─── Rate Limiting (Sliding Window) ───

    async def check_rate_limit(
        self,
        user_id: str,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Check and update rate limit using sliding window.
        Returns dict with 'allowed', 'remaining', 'reset_at'.
        """
        if not self.client:
            return {"allowed": True, "remaining": max_requests or 60, "reset_at": 0}

        max_requests = max_requests or settings.rate_limit_requests
        window_seconds = window_seconds or settings.rate_limit_window_seconds
        key = f"ratelimit:{user_id}"
        now = time.time()
        window_start = now - window_seconds

        try:
            pipe = self.client.pipeline()
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Count requests in window
            pipe.zcard(key)
            # Set expiry on the key
            pipe.expire(key, window_seconds)

            results = await pipe.execute()
            request_count = results[2]

            allowed = request_count <= max_requests
            remaining = max(0, max_requests - request_count)
            reset_at = now + window_seconds

            return {
                "allowed": allowed,
                "remaining": remaining,
                "reset_at": reset_at,
                "request_count": request_count,
            }
        except Exception as e:
            logger.warning(f"Rate limit check error: {e}")
            return {"allowed": True, "remaining": max_requests, "reset_at": 0}

    # ─── Metrics ───

    async def increment_counter(self, name: str, amount: int = 1):
        """Increment a metrics counter."""
        if not self.client:
            return
        try:
            await self.client.incrby(f"metrics:{name}", amount)
        except Exception as e:
            logger.warning(f"Redis counter increment error: {e}")

    async def get_counter(self, name: str) -> int:
        """Get current counter value."""
        if not self.client:
            return 0
        try:
            value = await self.client.get(f"metrics:{name}")
            return int(value) if value else 0
        except Exception as e:
            logger.warning(f"Redis counter get error: {e}")
            return 0

    async def store_latency(self, endpoint: str, latency_ms: float):
        """Store latency measurement for metrics."""
        if not self.client:
            return
        try:
            key = f"latency:{endpoint}"
            await self.client.lpush(key, latency_ms)
            await self.client.ltrim(key, 0, 999)  # Keep last 1000 measurements
        except Exception as e:
            logger.warning(f"Redis latency store error: {e}")

    async def get_latency_stats(self, endpoint: str) -> Dict[str, float]:
        """Get latency statistics for an endpoint."""
        if not self.client:
            return {}
        try:
            key = f"latency:{endpoint}"
            values = await self.client.lrange(key, 0, -1)
            if not values:
                return {}
            floats = [float(v) for v in values]
            floats.sort()
            n = len(floats)
            return {
                "count": n,
                "p50": floats[n // 2],
                "p95": floats[int(n * 0.95)],
                "p99": floats[int(n * 0.99)],
                "avg": sum(floats) / n,
                "min": floats[0],
                "max": floats[-1],
            }
        except Exception as e:
            logger.warning(f"Redis latency stats error: {e}")
            return {}


# Singleton
redis_client = RedisClient()
