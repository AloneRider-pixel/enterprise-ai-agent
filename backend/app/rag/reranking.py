"""
Cross-encoder reranking for retrieved chunks.
Improves retrieval quality by re-scoring chunks with a more powerful model.
"""
import logging
from typing import Dict, List, Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class RerankerService:
    """
    Cross-encoder reranking service.
    
    Uses a cross-encoder model to re-score (query, chunk) pairs
    for improved relevance after initial retrieval.
    
    Falls back to score-based reranking if cross-encoder is unavailable.
    """

    def __init__(self, top_n: int = None):
        self.top_n = top_n or settings.rerank_top_n
        self._model = None

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("Cross-encoder reranker model loaded")
            except Exception as e:
                logger.warning(f"Failed to load cross-encoder model: {e}. Using fallback.")
                self._model = None

    async def rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_n: Optional[int] = None,
    ) -> List[Dict]:
        """
        Rerank retrieved chunks using cross-encoder.
        
        Args:
            query: Original query
            chunks: Retrieved chunks with content and scores
            top_n: Number of top results to return
        
        Returns:
            Reranked list of chunks with updated scores
        """
        top_n = top_n or self.top_n

        if not chunks:
            return []

        if len(chunks) <= top_n:
            return chunks

        # Try cross-encoder reranking
        try:
            self._load_model()
            if self._model is not None:
                return self._cross_encoder_rerank(query, chunks, top_n)
        except Exception as e:
            logger.warning(f"Cross-encoder reranking failed: {e}. Using fallback.")

        # Fallback: weighted score reranking
        return self._fallback_rerank(query, chunks, top_n)

    def _cross_encoder_rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_n: int,
    ) -> List[Dict]:
        """Rerank using cross-encoder model."""
        # Create (query, chunk_content) pairs
        pairs = [(query, chunk["content"]) for chunk in chunks]
        
        # Get cross-encoder scores
        ce_scores = self._model.predict(pairs)
        
        # Combine CE score with original retrieval score
        reranked = []
        for i, chunk in enumerate(chunks):
            combined_score = 0.7 * float(ce_scores[i]) + 0.3 * chunk.get("score", 0)
            reranked.append({
                **chunk,
                "score": combined_score,
                "rerank_score": float(ce_scores[i]),
                "original_score": chunk.get("score", 0),
            })
        
        # Sort by combined score descending
        reranked.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"Cross-encoder reranking complete: {len(chunks)} -> {top_n} chunks")
        return reranked[:top_n]

    def _fallback_rerank(
        self,
        query: str,
        chunks: List[Dict],
        top_n: int,
    ) -> List[Dict]:
        """
        Fallback reranking using keyword overlap + original score.
        Used when cross-encoder model is unavailable.
        """
        query_terms = set(query.lower().split())
        
        reranked = []
        for chunk in chunks:
            content_terms = set(chunk["content"].lower().split())
            
            # Keyword overlap score
            overlap = len(query_terms & content_terms)
            keyword_score = overlap / max(len(query_terms), 1)
            
            # Length penalty (prefer medium-length chunks)
            content_len = len(chunk["content"])
            length_factor = 1.0
            if content_len < 50:
                length_factor = 0.8
            elif content_len > 1000:
                length_factor = 0.9
            
            # Combined score
            combined_score = (
                0.5 * chunk.get("score", 0) +
                0.3 * keyword_score +
                0.2 * length_factor
            )
            
            reranked.append({
                **chunk,
                "score": combined_score,
                "keyword_overlap_score": keyword_score,
                "original_score": chunk.get("score", 0),
            })
        
        # Sort by combined score descending
        reranked.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(f"Fallback reranking complete: {len(chunks)} -> {top_n} chunks")
        return reranked[:top_n]


# Singleton
reranker_service = RerankerService()
