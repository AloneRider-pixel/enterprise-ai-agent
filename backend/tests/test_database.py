"""Tests for database-backed retrieval queries."""
import pytest

from app.database import VectorStore


class RecordingPool:
    """Minimal asyncpg pool stand-in that records the executed query."""

    def __init__(self):
        self.query = None
        self.arguments = None

    async def fetch(self, query, *arguments):
        self.query = query
        self.arguments = arguments
        return []


@pytest.mark.asyncio
async def test_hybrid_search_ranks_keyword_candidates_before_fusion():
    """Hybrid fusion must receive the highest-ranking keyword matches."""
    store = VectorStore()
    pool = RecordingPool()
    store.pool = pool

    await store.hybrid_search(
        query="account password reset",
        query_embedding=[0.1, 0.2],
        top_k=5,
    )

    keyword_cte = pool.query.split("keyword_results AS", 1)[1].split("combined AS", 1)[0]
    assert "ORDER BY keyword_score DESC" in keyword_cte
    assert pool.arguments[1] == 5
