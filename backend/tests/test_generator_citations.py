"""Tests for page-aware citation metadata in the RAG generator.

Pure unit tests over RAGGenerator._build_context: no OpenAI calls.
"""
from app.rag.generator import RAGGenerator


def _chunk(**overrides):
    chunk = {
        "chunk_id": "chunk-1",
        "document_id": "doc-9",
        "content": "Refunds are available within 30 days of purchase.",
        "score": 0.9,
        "metadata": {
            "filename": "handbook.pdf",
            "page_number": 1,
            "kind": "text",
        },
    }
    chunk.update(overrides)
    return chunk


class TestCitationMetadata:
    def setup_method(self):
        self.generator = RAGGenerator()

    def test_sources_carry_page_provenance(self):
        context, sources = self.generator._build_context([_chunk()])
        source = sources[0]
        assert source["filename"] == "handbook.pdf"
        assert source["page_number"] == 1
        assert source["kind"] == "text"
        assert source["page_image_url"] == "/api/documents/doc-9/pages/1/image"

    def test_context_header_names_file_and_page(self):
        context, _ = self.generator._build_context([_chunk()])
        assert "[Source 1] (handbook.pdf, page 1, Score: 0.900)" in context

    def test_table_kind_is_labelled(self):
        chunk = _chunk(metadata={
            "filename": "pricing.pdf",
            "page_number": 2,
            "kind": "table",
        })
        context, sources = self.generator._build_context([chunk])
        assert "page 2" in context and "table" in context
        assert sources[0]["kind"] == "table"

    def test_chunks_without_page_metadata_keep_working(self):
        chunk = _chunk(metadata={})
        context, sources = self.generator._build_context([chunk])
        assert sources[0]["page_number"] is None
        assert sources[0]["page_image_url"] is None
        assert "[Source 1] (Score: 0.900)" in context

    def test_missing_metadata_key_keep_working(self):
        chunk = _chunk()
        del chunk["metadata"]
        _, sources = self.generator._build_context([chunk])
        assert sources[0]["page_image_url"] is None
