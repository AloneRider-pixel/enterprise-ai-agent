# Contributing to Enterprise AI Agent

This repository is an enterprise-style RAG and tool-calling application.

## Development workflow

1. Create a focused branch from `main`.
2. Add or update backend/frontend tests for behavior changes.
3. Keep RAG and agent evaluation reproducible and document evaluation data and scoring.
4. Run lint, tests, and application builds locally before opening a pull request.
5. Never commit API keys, credentials, private documents, or generated secrets.

## Quality expectations

- Keep authentication, authorization, input validation, and rate limiting intact.
- Preserve source citations for retrieval-backed responses.
- Prefer deterministic tests for business logic and isolate external model/API calls.
- Document important agent, retrieval, and infrastructure trade-offs.

## Pull requests

Include affected components, tests executed, evaluation impact, and any security or cost implications.
