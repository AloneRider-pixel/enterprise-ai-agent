"""Tests for the optional invite-code gate and the global daily model-call cap."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.redis_client import RedisClient


class FakeRedis:
    """Minimal in-memory stand-in for the Redis calls the cap uses."""

    def __init__(self, fail=False):
        self.store = {}
        self.fail = fail

    async def incrby(self, key, n):
        if self.fail:
            raise RuntimeError("redis down")
        self.store[key] = self.store.get(key, 0) + n
        return self.store[key]

    async def decrby(self, key, n):
        self.store[key] -= n

    async def expire(self, key, ttl):
        return True


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _body():
    return {
        "email": f"{uuid.uuid4().hex}@example.com",
        "password": "securepass123",
        "full_name": "Invite Test",
    }


async def test_register_open_when_no_invite_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "registration_invite_code", None)
    r = await client.post("/api/auth/register", json=_body())
    assert r.status_code == 201


async def test_register_rejected_without_or_with_wrong_code(client, monkeypatch):
    monkeypatch.setattr(settings, "registration_invite_code", "let-me-in")
    assert (await client.post("/api/auth/register", json=_body())).status_code == 403
    r = await client.post("/api/auth/register", json=_body(), headers={"X-Invite-Code": "nope"})
    assert r.status_code == 403


async def test_register_accepted_with_correct_code(client, monkeypatch):
    monkeypatch.setattr(settings, "registration_invite_code", "let-me-in")
    r = await client.post("/api/auth/register", json=_body(), headers={"X-Invite-Code": "let-me-in"})
    assert r.status_code == 201


async def test_cap_unset_allows(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", None)
    c = RedisClient()
    c.client = None
    assert await c.reserve_model_calls(5) is True


async def test_cap_enforced_globally(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", 3)
    c = RedisClient()
    c.client = FakeRedis()
    assert await c.reserve_model_calls(2) is True
    assert await c.reserve_model_calls(1) is True
    assert await c.reserve_model_calls(1) is False
    assert list(c.client.store.values()) == [3]  # rejected units are released


async def test_cap_fails_closed_without_redis(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", 3)
    c = RedisClient()
    c.client = None
    assert await c.reserve_model_calls(1) is False
    c.client = FakeRedis(fail=True)
    assert await c.reserve_model_calls(1) is False
