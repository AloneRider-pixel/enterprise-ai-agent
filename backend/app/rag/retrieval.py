"""
Hybrid retrieval combining vector similarity and keyword search.
Supports configurable weighting and result fusion.
"""
import logging
from typing import Dict, List, Optional

from app.config import settings
from app.database import vector_store
from app.rag.embeddings import embedding_service

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    Hybrid retrieval service combining:
    - Dense vector search (semantic similarity)
    - Sparse keyword search (BM25 via PostgreSQL full-text)
    - Score fusion with configurable weights
    """

    def __init__(
        self,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        top_k: int = None,
        similarity_threshold: float = None,
    ):
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.top_k = top_k or settings.retrieval_top_k
        self.similarity_threshold = similarity_threshold or settings.similarity_threshold

    async def retrieve(
        self,
        query: str,
        method: str = "hybrid",
        top_k: Optional[int] = None,
    ) -> Dict:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User query text
            method: "vector", "keyword", or "hybrid"
            top_k: Number of results to return
        
        Returns:
            Dict with query, chunks, retrieval_method, total_chunks_found
        """
        top_k = top_k or self.top_k
        
        if method == "vector":
            return await self._vector_retrieve(query, top_k)
        elif method == "keyword":
            return await self._keyword_retrieve(query, top_k)
        else:
            return await self._hybrid_retrieve(query, top_k)

    async def _vector_retrieve(self, query: str, top_k: int) -> Dict:
        """Dense vector similarity search."""
        # Generate query embedding
        query_embedding = await embedding_service.embed_text(query)
        
        # Search pgvector
        results = await vector_store.vector_search(
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=self.similarity_threshold,
        )
        
        chunks = self._format_results(results)
        
        logger.info(f"Vector retrieval: found {len(chunks)} chunks for query")
        return {
            "query": query,
            "chunks": chunks,
            "retrieval_method": "vector",
            "total_chunks_found": len(chunks),
        }

    async def _keyword_retrieve(self, query: str, top_k: int) -> Dict:
        """BM25-style keyword search via PostgreSQL full-text."""
        results = await vector_store.keyword_search(
            query=query,
            top_k=top_k,
        )
        
        chunks = self._format_results(results)
        
        logger.info(f"Keyword retrieval: found {len(chunks)} chunks for query")
        return {
            "query": query,
            "chunks": chunks,
            "retrieval_method": "keyword",
            "total_chunks_found": len(chunks),
        }

    async def _hybrid_retrieve(self, query: str, top_k: int) -> Dict:
        """Combined vector + keyword search with score fusion."""
        # Generate query embedding
        query_embedding = await embedding_service.embed_text(query)
        
        # Hybrid search in database
        results = await vector_store.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=top_k,
            vector_weight=self.vector_weight,
            keyword_weight=self.keyword_weight,
        )
        
        chunks = self._format_results(results)
        
        logger.info(
            f"Hybrid retrieval: found {len(chunks)} chunks "
            f"(vector_weight={self.vector_weight}, keyword_weight={self.keyword_weight})"
        )
        return {
            "query": query,
            "chunks": chunks,
            "retrieval_method": "hybrid",
            "total_chunks_found": len(chunks),
        }

    def _format_results(self, results: List[dict]) -> List[Dict]:
        """Format database results into standardized chunk dicts."""
        chunks = []
        for row in results:
            chunks.append({
                "chunk_id": str(row.get("id", "")),
                "document_id": str(row.get("document_id", "")),
                "content": row.get("content", ""),
                "score": float(row.get("similarity", row.get("rank", row.get("score", 0)))),
                "metadata": row.get("metadata", {}),
            })
        return chunks


# Singleton
retrieval_service = RetrievalService()
