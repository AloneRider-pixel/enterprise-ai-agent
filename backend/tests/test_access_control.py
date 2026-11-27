"""Tests for the optional invite-code gate and the global daily model-call cap."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app import usage_cap
from app.database import engine
from sqlalchemy import text


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


async def _reset():
    async with engine.begin() as conn:
        await conn.execute(usage_cap._CREATE)
        await conn.execute(text("DELETE FROM model_call_usage"))


async def _used():
    async with engine.begin() as conn:
        return (await conn.execute(text("SELECT COALESCE(SUM(used),0) FROM model_call_usage"))).scalar()


async def test_cap_unset_allows(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", None)
    assert await usage_cap.reserve_model_calls(5) is True


async def test_cap_enforced_and_rejection_leaves_counter(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", 3)
    await _reset()
    assert await usage_cap.reserve_model_calls(2) is True
    assert await usage_cap.reserve_model_calls(1) is True
    assert await usage_cap.reserve_model_calls(1) is False
    assert await _used() == 3


async def test_oversized_first_request_denied(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", 3)
    await _reset()
    assert await usage_cap.reserve_model_calls(4) is False
    assert await _used() == 0


async def test_concurrent_reservations_never_exceed_cap(monkeypatch):
    import asyncio
    monkeypatch.setattr(settings, "daily_model_call_cap", 5)
    await _reset()
    res = await asyncio.gather(*[usage_cap.reserve_model_calls(1) for _ in range(20)])
    assert sum(res) == 5
    assert await _used() == 5


async def test_cap_fails_closed_on_db_error(monkeypatch):
    monkeypatch.setattr(settings, "daily_model_call_cap", 3)

    class Boom:
        def begin(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(usage_cap, "engine", Boom())
    assert await usage_cap.reserve_model_calls(1) is False
