# ForgeAI — AI Software Engineering Platform

ForgeAI is a production-oriented engineering agent that reviews GitHub pull requests, analyzes change risk, checks security-sensitive patterns, evaluates test impact, and produces a deterministic review report.

The first release is intentionally an engineering system rather than a chatbot: it has a stable analysis core, typed domain models, policy gates, tests, container support, and CI.

## Architecture

```text
GitHub PR URL
     |
     v
FastAPI API
     |
     +--> GitHub client ---------> GitHub REST API
     |
     v
Change Analyzer
     |
     +--> file risk classification
     +--> test-impact analysis
     +--> dependency-change detection
     |
     v
Risk Engine
     |
     +--> weighted risk score
     +--> policy gate
     +--> severity findings
     |
     v
Typed Review Report
```

## Current capabilities

- Fetch public pull-request metadata and changed files from GitHub.
- Detect high-risk areas such as authentication, authorization, payments, infrastructure, migrations, and workflow changes.
- Detect missing or weak test coverage heuristically from changed paths.
- Detect dependency-file changes and surface compatibility review guidance.
- Produce a deterministic 0–100 risk score with explainable factors.
- Apply a configurable merge-gate policy.
- Expose the review through a FastAPI endpoint.
- Run locally without an LLM key.

## API

### `GET /health`

Returns service status.

### `POST /v1/reviews`

```json
{
  "repository": "octocat/hello-world",
  "pull_request": 42
}
```

Returns a typed review containing risk score, gate decision, findings, and analysis factors.

### `GET /docs`

Interactive OpenAPI documentation.

## Engineering decisions

1. **Deterministic core first** — the baseline analyzer is explainable and testable without a model provider.
2. **Provider-independent domain layer** — future LLM agents can sit behind a service boundary instead of controlling the entire application.
3. **Risk as a policy primitive** — the score is accompanied by explicit factors and a gate decision.
4. **GitHub as an adapter** — external API details stay out of the analysis engine.
5. **Fail closed on malformed upstream data** — invalid upstream payloads are rejected rather than partially analyzed.

## Roadmap

- LangGraph-based planning agent with explicit tool permissions.
- GitHub Actions tool for test execution and artifact collection.
- CodeQL and dependency-review result ingestion.
- Semantic code search and repository context via embeddings.
- MCP-based tool gateway with allowlisted capabilities.
- LLM review generation with structured outputs.
- Offline benchmark suite over seeded repositories.
- OpenTelemetry traces, Prometheus metrics, and cost/latency dashboards.
- Human approval workflow before merge automation.

## Run locally

```bash
cd forgeai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

Open `http://localhost:8000/docs`.

## Tests

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

## License

MIT
