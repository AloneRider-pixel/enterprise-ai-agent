# Engineering Notes

## Engineering focus
An enterprise-style AI support platform combining RAG, tool calling, conversation memory, streaming, safety controls, evaluation, and observability.

## Key design decisions
- **Hybrid RAG:** combines semantic retrieval and keyword search before reranking.
- **Tool-calling agent:** separates knowledge retrieval from operational actions such as order lookup and escalation.
- **Human/safety boundaries:** authentication, rate limiting, prompt-injection defenses, and verification are explicit concerns.
- **Streaming API:** SSE provides incremental responses to the frontend.
- **Evaluation and cost telemetry:** response quality, latency, and token cost are measurable.
- **Containerized delivery:** backend and frontend have independent Docker build paths.

## Verification checklist
- Start the stack with Docker Compose.
- Seed sample documents.
- Test retrieval and citations.
- Exercise tool calls and escalation paths.
- Run the evaluation suite and inspect latency/cost metrics.

## Portfolio note
Performance and evaluation numbers should be presented only when reproduced by the current evaluation harness.
