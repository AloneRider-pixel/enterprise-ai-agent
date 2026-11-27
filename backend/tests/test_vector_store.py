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


async def test_search_finds_rows_with_ivfflat_index_built_on_empty_table(store):
    """init_database builds an ivfflat index (lists=100) on an empty table.
    Without ivfflat.probes raised, a small table returns zero rows."""
    import random

    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text("DROP INDEX IF EXISTS chunk_embedding_idx"))
        await conn.execute(text("TRUNCATE document_chunks CASCADE"))
        await conn.execute(
            text(
                "CREATE INDEX chunk_embedding_idx ON document_chunks "
                "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )
        )
        doc_id = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO documents (id, filename, file_type, file_size, content_hash, status, "
                "chunk_count, metadata, created_at) VALUES (:id, 'p.txt', 'text', 1, :h, 'uploaded', 0, '{}'::jsonb, NOW())"
            ),
            {"id": doc_id, "h": uuid.uuid4().hex},
        )
    rnd = random.Random(7)
    dims = settings.openai_embedding_dimensions
    stored = [rnd.gauss(0, 1) for _ in range(dims)]
    query = [rnd.gauss(0, 1) for _ in range(dims)]
    await store.store_embedding(
        chunk_id=str(uuid.uuid4()),
        document_id=str(doc_id),
        content="shipping takes three to five business days",
        embedding=stored,
        metadata={"chunk_index": 0, "filename": "p.txt"},
    )
    # Several unrelated query vectors: with default probes this is hit-or-miss.
    for _ in range(8):
        query = [rnd.gauss(0, 1) for _ in range(dims)]
        vec_rows = await store.vector_search(query, top_k=5, similarity_threshold=-1.0)
        assert len(vec_rows) == 1
        hybrid_rows = await store.hybrid_search(query="zzz unrelated words", query_embedding=query, top_k=5)
        assert len(hybrid_rows) == 1
