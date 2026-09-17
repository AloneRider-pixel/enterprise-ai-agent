# Enterprise AI Agent Architecture

```mermaid
flowchart LR
    UI[React Chat UI] --> API[FastAPI REST + SSE]
    API --> AUTH[JWT Auth / Rate Limit]
    API --> AGENT[LangGraph Agent]
    AGENT --> RET[Hybrid Retrieval + Reranking]
    RET --> VDB[(PostgreSQL + pgvector)]
    AGENT --> TOOLS[Order / Refund / Search / Escalation Tools]
    API --> REDIS[(Redis Memory + Cache)]
    AGENT --> LLM[LLM Provider]
    API --> OBS[Structured Logs / Metrics]
```

## Reliability and safety

- Retrieval responses retain source-document citations.
- Tool access is separated from free-form generation.
- Authentication and rate limiting protect application endpoints.
- External model calls remain observable through latency, token, and cost metrics.
- Evaluation covers faithfulness, relevance, recall, precision, latency, and cost.
