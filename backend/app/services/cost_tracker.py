"""
Token and cost tracking service.
Tracks per-request and cumulative costs for all LLM calls.
"""
import logging
import time
from datetime import datetime, date
from typing import Dict, Optional

from app.config import settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)


# Token pricing per 1K tokens
PRICING = {
    "gpt-4o-mini": {
        "input": 0.00015,   # $0.15 per 1M tokens = $0.00015 per 1K
        "output": 0.0006,   # $0.60 per 1M tokens = $0.0006 per 1K
    },
    "gpt-4o": {
        "input": 0.0025,    # $2.50 per 1M tokens
        "output": 0.01,     # $10.00 per 1M tokens
    },
    "text-embedding-3-small": {
        "input": 0.00002,   # $0.02 per 1M tokens
        "output": 0.0,
    },
    "text-embedding-3-large": {
        "input": 0.00013,   # $0.13 per 1M tokens
        "output": 0.0,
    },
}


class CostTracker:
    """
    Tracks token usage and costs across the platform.
    Stores metrics in Redis for real-time access.
    """

    async def track_request(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict:
        """
        Track token usage and calculate cost for a single request.
        
        Returns dict with tokens, cost, and cumulative stats.
        """
        pricing = PRICING.get(model, PRICING["gpt-4o-mini"])
        
        # Calculate cost
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Update Redis counters
        today = date.today().isoformat()
        
        await redis_client.increment_counter("total_input_tokens", input_tokens)
        await redis_client.increment_counter("total_output_tokens", output_tokens)
        await redis_client.increment_counter(
            "total_cost_millis", int(total_cost * 1_000_000)
        )
        await redis_client.increment_counter(f"daily_tokens:{today}", input_tokens + output_tokens)
        
        if user_id:
            await redis_client.increment_counter(f"user_tokens:{user_id}", input_tokens + output_tokens)
            await redis_client.increment_counter(
                f"user_cost_millis:{user_id}", int(total_cost * 1_000_000)
            )
        
        if session_id:
            await redis_client.increment_counter(f"session_tokens:{session_id}", input_tokens + output_tokens)
        
        # Check alert threshold
        total_cost_usd = await self.get_total_cost()
        if total_cost_usd > settings.cost_alert_threshold_usd:
            logger.warning(
                f"Cost alert: Total cost ${total_cost_usd:.2f} "
                f"exceeds threshold ${settings.cost_alert_threshold_usd:.2f}"
            )
        
        result = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": total_cost,
            "cumulative_cost_usd": total_cost_usd,
        }
        
        logger.info(
            f"Cost tracked: model={model}, tokens={input_tokens + output_tokens}, "
            f"cost=${total_cost:.6f}"
        )
        
        return result

    async def get_total_cost(self) -> float:
        """Get total cumulative cost in USD."""
        cost_millis = await redis_client.get_counter("total_cost_millis")
        return cost_millis / 1_000_000

    async def get_total_tokens(self) -> Dict[str, int]:
        """Get total cumulative token usage."""
        input_tokens = await redis_client.get_counter("total_input_tokens")
        output_tokens = await redis_client.get_counter("total_output_tokens")
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    async def get_user_stats(self, user_id: str) -> Dict:
        """Get token usage and cost stats for a user."""
        user_tokens = await redis_client.get_counter(f"user_tokens:{user_id}")
        user_cost_millis = await redis_client.get_counter(f"user_cost_millis:{user_id}")
        
        return {
            "user_id": user_id,
            "total_tokens": user_tokens,
            "total_cost_usd": user_cost_millis / 1_000_000,
        }

    async def get_daily_stats(self) -> Dict:
        """Get today's usage statistics."""
        today = date.today().isoformat()
        daily_tokens = await redis_client.get_counter(f"daily_tokens:{today}")
        
        return {
            "date": today,
            "total_tokens": daily_tokens,
            "total_cost_usd": await self.get_total_cost(),
        }


# Singleton
cost_tracker = CostTracker()
