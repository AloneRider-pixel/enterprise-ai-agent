"""Opt-in real database regression. No API/embedding-model calls."""
import os
import uuid

import pytest

from app.database import VectorStore, init_database


@pytest.mark.skipif(os.getenv('RUN_DB_TESTS') != '1', reason='requires a disposable Postgres/pgvector test database')
@pytest.mark.asyncio
async def test_real_chunk_roundtrip_and_fresh_index_retrieval():
    await init_database()
    store = VectorStore()
    await store.connect()
    document_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    embedding = [1.0] + [0.0] * 1535
    metadata = {'filename': 'fixture.pdf', 'page_number': 2, 'kind': 'image'}
    try:
        await store.pool.execute('''
            INSERT INTO documents (id,filename,file_type,file_size,content_hash,status,
                                   chunk_count,metadata,created_at)
            VALUES ($1,'fixture.pdf','pdf',1,$2,'indexed',1,'{}'::jsonb,NOW())
        ''', document_id, uuid.uuid4().hex)
        await store.store_embedding(str(chunk_id), str(document_id),
                                    'Escalation: press the red button', embedding,
                                    metadata, chunk_index=7)
        rows = await store.vector_search(embedding, top_k=100, similarity_threshold=0.99)
        hit = next(row for row in rows if str(row['id']) == str(chunk_id))
        assert hit['metadata'] == metadata
        keyword_rows = await store.keyword_search('escalation button', top_k=100)
        assert any(str(row['id']) == str(chunk_id) for row in keyword_rows)
        row = await store.pool.fetchrow(
            'SELECT chunk_index,created_at,updated_at FROM document_chunks WHERE id=$1', chunk_id)
        assert row['chunk_index'] == 7
        assert row['created_at'] and row['updated_at']
    finally:
        await store.pool.execute('DELETE FROM document_chunks WHERE document_id=$1', document_id)
        await store.pool.execute('DELETE FROM documents WHERE id=$1', document_id)
        await store.disconnect()
