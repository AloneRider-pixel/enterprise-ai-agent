"""Global daily model-call cap stored in Postgres.

One row per UTC day. The reservation is a single atomic statement, so
concurrent requests can never push the day's total over the cap, and a
rejected request leaves the counter unchanged. When a cap is configured,
any database error denies the call (fails closed).
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

_CREATE = text(
    "CREATE TABLE IF NOT EXISTS model_call_usage ("
    "day DATE PRIMARY KEY, used INTEGER NOT NULL)"
)

# Insert the day's first row only if it fits; otherwise raise the counter only
# if the new total still fits. No row returned means the reservation is denied.
_RESERVE = text(
    """
    INSERT INTO model_call_usage (day, used)
    SELECT CAST(:day AS DATE), CAST(:n AS INTEGER) WHERE CAST(:n AS INTEGER) <= CAST(:cap AS INTEGER)
    ON CONFLICT (day) DO UPDATE
        SET used = model_call_usage.used + CAST(:n AS INTEGER)
        WHERE model_call_usage.used + CAST(:n AS INTEGER) <= CAST(:cap AS INTEGER)
    RETURNING used
    """
)


async def reserve_model_calls(units: int = 1) -> bool:
    """Reserve `units` of today's global model-call budget.

    True when no cap is configured or the units fit under it. With a cap
    configured, False when over the cap or when the database errors.
    """
    cap = settings.daily_model_call_cap
    if not cap or cap <= 0:
        return True
    if units <= 0:
        return True
    try:
        day = datetime.now(timezone.utc).date()
        async with engine.begin() as conn:
            await conn.execute(_CREATE)
            row = (
                await conn.execute(_RESERVE, {"day": day, "n": units, "cap": cap})
            ).first()
        return row is not None
    except Exception as e:
        logger.warning(f"Model-call cap check error (failing closed): {e}")
        return False
