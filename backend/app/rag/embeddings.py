"""
Embedding generation using OpenAI text-embedding models.
Handles batch embedding and caching for efficiency.
"""
import hashlib
import logging
from typing import List

import numpy as np
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

# OpenAI client
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


class EmbeddingService:
    """Generates text embeddings using OpenAI's embedding API."""

    def __init__(self):
        self.model = settings.openai_embedding_model
        self.dimensions = settings.openai_embedding_dimensions
        self._cache = {}  # Simple in-process cache for dedup

    def _content_hash(self, text: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.sha256(text.encode()).hexdigest()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        # Check cache first
        content_hash = self._content_hash(text)
        if content_hash in self._cache:
            return self._cache[content_hash]

        response = await openai_client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        embedding = response.data[0].embedding
        
        # Cache the result
        self._cache[content_hash] = embedding
        
        # Limit cache size
        if len(self._cache) > 10000:
            oldest_keys = list(self._cache.keys())[:1000]
            for k in oldest_keys:
                del self._cache[k]

        return embedding

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Embed multiple texts in batches for efficiency."""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Check which texts need embedding
            uncached_indices = []
            uncached_texts = []
            batch_results = [None] * len(batch)
            
            for j, text in enumerate(batch):
                content_hash = self._content_hash(text)
                if content_hash in self._cache:
                    batch_results[j] = self._cache[content_hash]
                else:
                    uncached_indices.append(j)
                    uncached_texts.append(text)
            
            # Embed uncached texts
            if uncached_texts:
                response = await openai_client.embeddings.create(
                    model=self.model,
                    input=uncached_texts,
                    dimensions=self.dimensions,
                )
                
                for idx, data in enumerate(response.data):
                    j = uncached_indices[idx]
                    batch_results[j] = data.embedding
                    # Cache
                    content_hash = self._content_hash(uncached_texts[idx])
                    self._cache[content_hash] = data.embedding

            all_embeddings.extend(batch_results)
            logger.info(f"Embedded batch {i // batch_size + 1}: {len(batch)} texts")

        return all_embeddings

    def get_token_cost(self, num_tokens: int) -> float:
        """Calculate cost for embedding tokens."""
        return num_tokens * settings.embedding_price


# Singleton
embedding_service = EmbeddingService()
