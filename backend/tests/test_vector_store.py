"""VectorStore against a real Postgres with pgvector (matches the CI service)."""
import uuid

import pytest

from app.config import settings
from app.database import Base, VectorStore, engine


@pytest.fixture
async def store():
    import app.models.database  # noqa: F401  (register tables)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    s = VectorStore()
    await s.connect()
    yield s
    await s.disconnect()


async def test_store_and_search_roundtrip(store):
    doc_id = uuid.uuid4()
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO documents (id, filename, file_type, file_size, content_hash, status, "
                "chunk_count, metadata, created_at) VALUES (:id, 't.txt', 'text', 1, :h, 'uploaded', 0, '{}'::jsonb, NOW())"
            ),
            {"id": doc_id, "h": uuid.uuid4().hex},
        )
    vec = [0.0] * settings.openai_embedding_dimensions
    vec[0] = 1.0
    chunk_id = str(uuid.uuid4())
    await store.store_embedding(
        chunk_id=chunk_id,
        document_id=str(doc_id),
        content="refund policy thirty days",
        embedding=vec,
        metadata={"chunk_index": 2, "filename": "t.txt"},
    )
    # upsert again, same id
    await store.store_embedding(
        chunk_id=chunk_id, document_id=str(doc_id), content="refund policy thirty days",
        embedding=vec, metadata={"chunk_index": 2, "filename": "t.txt"},
    )
    rows = await store.vector_search(vec, top_k=3, similarity_threshold=0.5)
    mine = [r for r in rows if str(r["id"]) == chunk_id]
    assert len(mine) == 1
    assert mine[0]["metadata"] == {"chunk_index": 2, "filename": "t.txt"}
    kw = await store.keyword_search("refund", top_k=3)
    assert any(str(r["id"]) == chunk_id for r in kw)
