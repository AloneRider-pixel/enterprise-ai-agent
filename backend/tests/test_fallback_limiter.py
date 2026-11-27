import asyncio
from types import SimpleNamespace

from app.redis_client import RedisClient


def test_local_limiter_blocks_after_max_when_redis_down():
    c = RedisClient()
    res = [asyncio.run(c.check_rate_limit("ip:1", max_requests=3, window_seconds=60)) for _ in range(5)]
    assert [r["allowed"] for r in res] == [True, True, True, False, False]
    assert res[3]["remaining"] == 0


def test_local_limiter_is_per_user():
    c = RedisClient()
    for _ in range(3):
        asyncio.run(c.check_rate_limit("a", max_requests=3, window_seconds=60))
    assert asyncio.run(c.check_rate_limit("b", max_requests=3, window_seconds=60))["allowed"]


def test_local_limiter_falls_back_on_redis_error():
    class Boom:
        def pipeline(self):
            raise RuntimeError("down")
    c = RedisClient()
    c.client = Boom()
    r = [asyncio.run(c.check_rate_limit("u", max_requests=1, window_seconds=60)) for _ in range(2)]
    assert [x["allowed"] for x in r] == [True, False]


def test_local_limiter_memory_bounded():
    c = RedisClient()
    for i in range(10050):
        c._local_rate_limit(f"k{i}", 5, 60)
    assert len(c._local_hits) <= 10001


def test_generator_empty_content_gets_fallback(monkeypatch):
    from app.rag import generator as g

    async def fake_create(**kw):
        msg = SimpleNamespace(content=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="length")], usage=None)

    monkeypatch.setattr(g.openai_client.chat.completions, "create", fake_create)
    out = asyncio.run(g.rag_generator.generate("q", [{"content": "c", "filename": "f", "chunk_index": 0, "score": 1.0}]))
    assert out["response"] and "couldn't generate" in out["response"]
