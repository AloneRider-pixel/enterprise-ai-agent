"""
Text chunking strategies for document processing.
Implements recursive character splitting with overlap preservation.
"""
import hashlib
import logging
import re
import uuid
from typing import Dict, List, Optional, Tuple

import tiktoken

from app.config import settings

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Recursive text chunking with configurable size and overlap.
    Preserves semantic boundaries (paragraphs, sentences) when possible.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
        
        # Token encoder for accurate sizing
        try:
            self.encoder = tiktoken.encoding_for_model("gpt-4o-mini")
        except Exception:
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Split text into overlapping chunks preserving semantic boundaries.
        
        Returns list of dicts with:
        - chunk_id: UUID
        - content: chunk text
        - chunk_index: sequential index
        - metadata: source metadata + chunk info
        """
        if not text or not text.strip():
            return []

        # Clean text
        text = self._clean_text(text)
        
        # Recursive split
        chunks = self._recursive_split(text, self.separators)
        
        # Add overlap between consecutive chunks
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks)

        # Build chunk objects
        result = []
        base_metadata = metadata or {}
        
        for idx, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_meta = {
                **base_metadata,
                "chunk_index": idx,
                "chunk_total": len(chunks),
                "char_count": len(chunk_text),
                "token_count": len(self.encoder.encode(chunk_text)),
            }
            result.append({
                "chunk_id": chunk_id,
                "content": chunk_text,
                "chunk_index": idx,
                "metadata": chunk_meta,
            })

        logger.info(
            f"Chunked text into {len(result)} chunks "
            f"(size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return result

    def _recursive_split(
        self,
        text: str,
        separators: List[str],
    ) -> List[str]:
        """Recursively split text using separator hierarchy."""
        if len(self.encoder.encode(text)) <= self.chunk_size:
            return [text] if text.strip() else []

        # Find appropriate separator
        separator = separators[-1]
        remaining_separators = []
        
        for i, sep in enumerate(separators):
            if sep in text:
                separator = sep
                remaining_separators = separators[i + 1:]
                break

        # Split on separator
        if separator:
            parts = text.split(separator)
        else:
            # Character-level fallback
            parts = [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        # Recursively split parts that are still too large
        result = []
        current_chunk = ""
        
        for part in parts:
            test_chunk = current_chunk + separator + part if current_chunk else part
            
            if len(self.encoder.encode(test_chunk)) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                # Save current chunk if non-empty
                if current_chunk.strip():
                    result.append(current_chunk.strip())
                
                # If single part exceeds chunk_size, recurse with next separators
                if len(self.encoder.encode(part)) > self.chunk_size and remaining_separators:
                    sub_chunks = self._recursive_split(part, remaining_separators)
                    result.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        # Don't forget the last chunk
        if current_chunk.strip():
            result.append(current_chunk.strip())

        return result

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """Add overlap text between consecutive chunks."""
        if len(chunks) <= 1:
            return chunks

        result = [chunks[0]]
        
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            current_chunk = chunks[i]
            
            # Get last N characters for overlap
            overlap_text = prev_chunk[-self.chunk_overlap:]
            
            # Prepend overlap to current chunk
            overlapped = overlap_text + " " + current_chunk
            result.append(overlapped)

        return result

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        # Normalize quotes
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        # Remove null bytes
        text = text.replace("\x00", "")
        return text.strip()

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))


# Singleton
text_chunker = TextChunker()
