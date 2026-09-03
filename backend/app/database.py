"""
PostgreSQL database setup with pgvector support.
Handles connection pooling, table creation, and vector operations.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional

import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# ─── SQLAlchemy Async Engine ───
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─── Base Model ───
class Base(DeclarativeBase):
    pass


# ─── Session Dependency ───
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Database Initialization ───
async def init_database():
    """Create tables and enable pgvector extension."""
    # Get a raw connection to run DDL
    conn = await asyncpg.connect(settings.database_url)
    try:
        # Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("pgvector extension enabled")

        # Create tables via SQLAlchemy metadata
        async with engine.begin() as db_conn:
            await db_conn.run_sync(Base.metadata.create_all)

        # Create vector index if not exists
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = 'document_chunks' AND indexname = 'chunk_embedding_idx'
                ) THEN
                    CREATE INDEX chunk_embedding_idx 
                    ON document_chunks 
                    USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = 100);
                END IF;
            END $$;
        """)
        logger.info("Database initialization complete")
    finally:
        await conn.close()


# ─── Raw pgvector Operations ───
class VectorStore:
    """Direct pgvector operations for RAG pipeline."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Initialize connection pool."""
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20,
        )

    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()

    async def store_embedding(
        self,
        chunk_id: str,
        document_id: str,
        content: str,
        embedding: List[float],
        metadata: dict,
    ):
        """Store a chunk embedding in pgvector."""
        await self.pool.execute(
            """
            INSERT INTO document_chunks (id, document_id, content, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            chunk_id,
            document_id,
            content,
            str(embedding),  # pgvector accepts string representation
            metadata,
        )

    async def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[dict]:
        """Semantic similarity search using pgvector."""
        rows = await self.pool.fetch(
            """
            SELECT 
                id,
                document_id,
                content,
                metadata,
                1 - (embedding <=> $1::vector) AS similarity
            FROM document_chunks
            WHERE 1 - (embedding <=> $1::vector) > $3
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            str(query_embedding),
            top_k,
            similarity_threshold,
        )
        return [dict(row) for row in rows]

    async def keyword_search(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[dict]:
        """Full-text search using PostgreSQL tsvector."""
        rows = await self.pool.fetch(
            """
            SELECT 
                id,
                document_id,
                content,
                metadata,
                ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
            FROM document_chunks
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
            ORDER BY rank DESC
            LIMIT $2
            """,
            query,
            top_k,
        )
        return [dict(row) for row in rows]

    async def hybrid_search(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> List[dict]:
        """Combined vector + keyword retrieval with score fusion."""
        rows = await self.pool.fetch(
            """
            WITH vector_results AS (
                SELECT 
                    id, document_id, content, metadata,
                    1 - (embedding <=> $1::vector) AS vector_score
                FROM document_chunks
                ORDER BY embedding <=> $1::vector
                LIMIT $2 * 2
            ),
            keyword_results AS (
                SELECT 
                    id, document_id, content, metadata,
                    ts_rank(to_tsvector('english', content), plainto_tsquery('english', $3)) AS keyword_score
                FROM document_chunks
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $3)
                LIMIT $2 * 2
            ),
            combined AS (
                SELECT 
                    COALESCE(v.id, k.id) AS id,
                    COALESCE(v.document_id, k.document_id) AS document_id,
                    COALESCE(v.content, k.content) AS content,
                    COALESCE(v.metadata, k.metadata) AS metadata,
                    COALESCE(v.vector_score, 0) * $4 + COALESCE(k.keyword_score, 0) * $5 AS score
                FROM vector_results v
                FULL OUTER JOIN keyword_results k ON v.id = k.id
            )
            SELECT id, document_id, content, metadata, score
            FROM combined
            ORDER BY score DESC
            LIMIT $2
            """,
            str(query_embedding),
            top_k,
            query,
            vector_weight,
            keyword_weight,
        )
        return [dict(row) for row in rows]

    async def get_document_chunks(self, document_id: str) -> List[dict]:
        """Get all chunks for a document."""
        rows = await self.pool.fetch(
            """
            SELECT id, content, metadata, created_at
            FROM document_chunks
            WHERE document_id = $1
            ORDER BY created_at
            """,
            document_id,
        )
        return [dict(row) for row in rows]

    async def delete_document_chunks(self, document_id: str):
        """Delete all chunks for a document."""
        await self.pool.execute(
            "DELETE FROM document_chunks WHERE document_id = $1",
            document_id,
        )


# Singleton instance
vector_store = VectorStore()
