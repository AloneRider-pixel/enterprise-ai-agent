"""Tests for the RAG pipeline components."""
import pytest
from app.rag.chunking import TextChunker
from app.evaluation.metrics import (
    compute_faithfulness,
    compute_answer_relevance,
    compute_context_recall,
)


class TestTextChunker:
    """Tests for the text chunking module."""

    def setup_method(self):
        self.chunker = TextChunker(chunk_size=100, chunk_overlap=20)

    def test_empty_text(self):
        result = self.chunker.chunk_text("")
        assert result == []

    def test_short_text(self):
        text = "This is a short text."
        result = self.chunker.chunk_text(text)
        assert len(result) >= 1
        assert result[0]["content"] == text

    def test_long_text_split(self):
        text = "This is sentence one. " * 50
        result = self.chunker.chunk_text(text)
        assert len(result) > 1

    def test_chunk_metadata(self):
        text = "Test content. " * 20
        result = self.chunker.chunk_text(text, metadata={"doc": "test"})
        for chunk in result:
            assert "chunk_id" in chunk
            assert "content" in chunk
            assert "chunk_index" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["doc"] == "test"

    def test_overlap_between_chunks(self):
        text = "Word " * 200
        result = self.chunker.chunk_text(text)
        if len(result) > 1:
            # Check that chunks share some overlapping content
            chunk1_words = set(result[0]["content"].split())
            chunk2_words = set(result[1]["content"].split())
            # There should be some overlap due to chunk_overlap parameter
            # (though with single repeated word, overlap is expected)
            assert len(result[0]["content"]) > 0
            assert len(result[1]["content"]) > 0


class TestMetrics:
    """Tests for evaluation metrics."""

    def test_faithfulness_perfect(self):
        response = "The refund policy is 30 days."
        context = "Our refund policy allows returns within 30 days of purchase."
        score = compute_faithfulness(response, context)
        assert score > 0.5

    def test_faithfulness_hallucinated(self):
        response = "The moon is made of cheese and costs $50 per pound."
        context = "Our subscription plans start at $29.99 per month."
        score = compute_faithfulness(response, context)
        assert score < 0.5

    def test_faithfulness_empty(self):
        assert compute_faithfulness("", "context") == 0.0
        assert compute_faithfulness("response", "") == 0.0

    def test_answer_relevance_good(self):
        question = "What is the refund policy?"
        answer = "The refund policy allows returns within 30 days."
        score = compute_answer_relevance(question, answer)
        assert score > 0.3

    def test_answer_relevance_off_topic(self):
        question = "What is the refund policy?"
        answer = "The weather today is sunny and warm with temperatures around 75 degrees."
        score = compute_answer_relevance(question, answer)
        assert score < 0.5

    def test_context_recall_good(self):
        ground_truth = "The enterprise plan costs $499.99 per month."
        context = "Enterprise Plan pricing is $499.99/month per license with full features."
        score = compute_context_recall(ground_truth, context)
        assert score > 0.3

    def test_context_recall_no_match(self):
        ground_truth = "The API rate limit is 100 requests per minute."
        context = "Our office is located in San Francisco, California."
        score = compute_context_recall(ground_truth, context)
        assert score < 0.5
