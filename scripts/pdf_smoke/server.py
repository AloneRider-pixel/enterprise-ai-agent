import os
from pathlib import Path
SMOKE_DIR = Path(os.environ.get("PDF_SMOKE_DIR", "/tmp/enterprise-pdf-smoke"))
SMOKE_DIR.mkdir(parents=True, exist_ok=True)
"""E2E backend: real Postgres+pgvector, hashing embeddings, mocked OpenAI chat."""
import os
os.environ.update({
    'SECRET_KEY': 'e2e-secret', 'JWT_SECRET_KEY': 'e2e-jwt', 'OPENAI_API_KEY': 'e2e',
    'APP_ENV': 'test', 'DEBUG': 'false',
    'POSTGRES_HOST': '127.0.0.1', 'POSTGRES_PORT': '5433',
    'POSTGRES_USER': 'test_user', 'POSTGRES_PASSWORD': 'test_password',
    'POSTGRES_DB': os.environ.get('PDF_SMOKE_DB', 'enterprise_pdf_smoke'),
    'REDIS_HOST': '127.0.0.1', 'REDIS_PORT': '6399',
    'PAGE_IMAGE_DIR': str(SMOKE_DIR / 'pages'),
    'ENABLE_PDF_IMAGE_CAPTIONS': 'false',
})
import hashlib, math, re
import httpx
from openai import AsyncOpenAI

DIM = 1536
def fake_embed(text):
    vec = [0.0] * DIM
    for tok in re.findall(r'[a-z0-9]+', text.lower()):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]

from app.rag import embeddings, generator, reranking
from app.services import hallucination
from app.rag.retrieval import retrieval_service
retrieval_service.similarity_threshold = 0.02

async def _embed_text(t): return fake_embed(t)
async def _embed_batch(ts): return [fake_embed(t) for t in ts]
embeddings.embedding_service.embed_text = _embed_text
embeddings.embedding_service.embed_batch = _embed_batch
reranking.reranker_service._load_model = lambda: None
hallucination.hallucination_detector._load_nli_model = lambda: None

# This transport is a fixture, NOT an LLM-quality check. Derive source
# identities from the actual retrieved prompt instead of assuming rank order.
import json

def respond(request):
    payload = json.loads(request.content)
    text = payload['messages'][-1]['content']
    parts = re.split(r'\[Source (\d+)\]', text)
    sources = [(int(parts[i]), parts[i+1]) for i in range(1,len(parts),2)]
    if 'red button' in text.lower() and 'escalation action' in text.lower():
        num, body = next((n,b) for n,b in sources if 'Text visible in image:' in b)
        assert 'press the red button' in body.lower()
        answer = f'The dashboard screenshot says to press the red button [Source {num}].'
    else:
        num, body = next((n,b) for n,b in sources if '| Basic |' in b and '| Pro |' in b)
        assert '$25' in body and 'Email' in body
        answer = f'The Pro plan costs $25 per month. Basic includes email support [Source {num}].'
    return httpx.Response(200, json={
        'id': 'e2e', 'object': 'chat.completion', 'created': 1, 'model': 'e2e-fixture',
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': answer},
                     'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})

generator.openai_client = AsyncOpenAI(
    api_key='e2e', http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    max_retries=0)

import uvicorn
from app.main import app
uvicorn.run(app, host='127.0.0.1', port=8000, log_level='warning')
