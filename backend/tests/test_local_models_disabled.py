"""DISABLE_LOCAL_MODELS must keep torch cross-encoders from loading."""
import sys

import pytest

from app.config import settings
from app.rag.reranking import RerankerService
from app.services.hallucination import HallucinationDetector


@pytest.fixture
def block_models(monkeypatch):
    monkeypatch.setattr(settings, "disable_local_models", True)
    monkeypatch.delitem(sys.modules, "sentence_transformers", raising=False)
    # Any attempt to import it fails loudly.
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)


@pytest.mark.asyncio
async def test_reranker_uses_fallback_without_loading_model(block_models):
    svc = RerankerService(top_n=2)
    chunks = [{"content": f"chunk {i} shipping", "score": 0.1 * i} for i in range(5)]
    out = await svc.rerank("shipping", chunks)
    assert len(out) == 2
    assert svc._model is None


@pytest.mark.asyncio
async def test_hallucination_uses_keyword_overlap_without_loading_model(block_models):
    det = HallucinationDetector()
    score = await det.detect(
        "Shipping takes three to five business days.",
        "Shipping takes three to five business days. Support hours are 9 to 5.",
    )
    assert 0.0 <= score <= 1.0
    assert det._nli_model is None
