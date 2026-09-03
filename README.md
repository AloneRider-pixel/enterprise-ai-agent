# 🤖 Enterprise AI Support & Knowledge Agent

**Production-grade RAG + AI Agent Platform** built with FastAPI, LangGraph, pgvector, and React.

An enterprise customer support agent that combines vector-based retrieval, tool calling, conversation memory, and safety guardrails — with full observability, evaluation, and CI/CD.

---

## 🏗️ Architecture

```
React (Streaming Chat UI)
    ↓
FastAPI (REST + SSE Streaming)
    ↓
LangGraph Agent
    ├── RAG Retrieval (Hybrid + Reranking)
    ├── Order Lookup Tool
    ├── Refund Tool
    ├── Web Search Tool
    └── Human Escalation Tool
          ↓
PostgreSQL + pgvector  |  Redis (Cache + Memory)
          ↓
        AWS (ECS / EC2)
```

## ✨ Features

### Core RAG Pipeline
- **Document Ingestion** — Upload PDFs, TXT, DOCX with automatic parsing
- **Intelligent Chunking** — Recursive text splitting with overlap preservation
- **Embeddings** — OpenAI `text-embedding-3-small` with pgvector storage
- **Hybrid Retrieval** — Combined vector similarity + BM25 keyword search
- **Reranking** — Cross-encoder reranking of retrieved chunks
- **Citation Tracking** — Every response includes source document references

### Agent Capabilities
- **Tool/Function Calling** — Order lookup, refund processing, search, escalation
- **Conversation Memory** — Redis-backed session memory with sliding window
- **Streaming Responses** — Server-Sent Events (SSE) for real-time token streaming
- **Multi-turn Reasoning** — LangGraph state machine for complex workflows

### Safety & Security
- **JWT Authentication** — Secure token-based auth with role-based access
- **Rate Limiting** — Per-user rate limits via Redis sliding window
- **Prompt Injection Protection** — Input sanitization and detection layer
- **Hallucination Detection** — NLI-based faithfulness verification

### Observability
- **Token & Cost Tracking** — Per-request OpenAI cost calculation
- **Latency Metrics** — End-to-end and per-stage timing
- **Structured Logging** — JSON logs with request tracing
- **RAG Evaluation** — Automated faithfulness, relevance, and recall scoring

### Infrastructure
- **Docker** — Multi-stage builds for backend and frontend
- **CI/CD** — GitHub Actions with linting, testing, and deployment
- **AWS Ready** — ECS Fargate deployment configuration

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, LangGraph, LangChain |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Frontend | React 18, Vite, TailwindCSS |
| Auth | JWT (PyJWT) |
| Monitoring | Structured JSON logging |
| CI/CD | GitHub Actions |
| Deployment | Docker, AWS ECS |

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API key

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/enterprise-ai-agent.git
cd enterprise-ai-agent
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

This starts:
- **Backend** → http://localhost:8000
- **Frontend** → http://localhost:3000
- **PostgreSQL** → localhost:5432
- **Redis** → localhost:6379

### 3. Create Admin User

```bash
docker-compose exec backend python -m app.scripts.create_admin
```

### 4. Seed Sample Documents

```bash
docker-compose exec backend python -m scripts.seed_documents
```

---

## 📁 Project Structure

```
enterprise-ai-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry
│   │   ├── config.py            # Settings & environment config
│   │   ├── database.py          # PostgreSQL + pgvector setup
│   │   ├── redis_client.py      # Redis connection & caching
│   │   ├── auth/                # JWT authentication
│   │   ├── models/              # Pydantic schemas & DB models
│   │   ├── agents/              # LangGraph agent, state, tools
│   │   ├── rag/                 # RAG pipeline (ingest→retrieve→generate)
│   │   ├── api/                 # API route handlers
│   │   ├── middleware/          # Rate limiting, logging, injection guard
│   │   ├── evaluation/          # RAG evaluation & metrics
│   │   └── services/            # Hallucination detection, cost tracking
│   ├── tests/                   # Pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── services/            # API client
│   │   └── hooks/               # Custom React hooks
│   ├── Dockerfile
│   └── package.json
├── evaluation/                  # Evaluation datasets & results
├── scripts/                     # Seed & utility scripts
├── .github/workflows/ci.yml    # GitHub Actions CI/CD
├── docker-compose.yml
└── .env.example
```

---

## 🔌 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/auth/me` | Get current user |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message (streaming SSE) |
| GET | `/api/chat/history/{session_id}` | Get conversation history |
| DELETE | `/api/chat/history/{session_id}` | Clear session |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload document |
| GET | `/api/documents` | List documents |
| DELETE | `/api/documents/{id}` | Delete document |
| POST | `/api/documents/ingest/{id}` | Trigger ingestion |

### Admin & Evaluation
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/metrics` | System metrics |
| POST | `/api/evaluation/run` | Run evaluation suite |
| GET | `/api/evaluation/results` | Get evaluation results |

---

## 📊 Evaluation

The platform includes a built-in evaluation framework that measures:

- **Faithfulness** — Is the response grounded in retrieved context?
- **Answer Relevance** — Does the response address the user's question?
- **Context Recall** — Did retrieval find the relevant documents?
- **Context Precision** — Are the top results actually relevant?
- **Latency** — End-to-end response time
- **Cost** — Token usage and dollar cost per query

Run evaluation:
```bash
docker-compose exec backend python -m scripts.run_evaluation
```

---

## 🔒 Security

- All passwords hashed with bcrypt
- JWT tokens with configurable expiry
- Rate limiting: 60 requests/minute per user
- Prompt injection detection using keyword + pattern matching
- Hallucination detection with NLI cross-verification
- CORS configured for production origins
- Input validation on all endpoints

---

## 📈 Performance Targets

| Metric | Target |
|--------|--------|
| P50 Latency | < 2s |
| P95 Latency | < 5s |
| Faithfulness Score | > 0.85 |
| Context Recall | > 0.80 |
| Hallucination Rate | < 5% |

---

## 📝 License

MIT
