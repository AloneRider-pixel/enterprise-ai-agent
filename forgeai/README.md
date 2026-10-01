# ForgeAI — Embedded Engineering Review Core

This directory contains the focused ForgeAI implementation embedded in the Enterprise AI Agent repository. It is intentionally kept independently testable from the parent application's optional model-assisted behavior.

## Purpose

ForgeAI reviews GitHub pull-request changes using deterministic risk rules and typed analysis outputs. It treats repository content as untrusted data and keeps side-effecting automation behind policy boundaries.

## Core flow

```text
GitHub PR
  ↓
Change analysis
  ├── security-sensitive paths
  ├── dependency changes
  ├── test impact
  └── secret-like patterns
  ↓
Risk engine
  ↓
Typed review report
```

## Local development

From the repository root:

```bash
cd forgeai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn forgeai.main:app --reload
```

## Verification

```bash
ruff check src tests scripts migrations
pytest
alembic upgrade head
python scripts/run_eval.py
python scripts/run_security_eval.py
```

These are aligned with the parent repository CI quality gates.

## Security

Do not execute repository content during analysis. Preserve webhook verification, input bounding, secret redaction, deterministic policy rules, and approval gates when extending GitHub/tool integrations.

## Review path

Review `src/forgeai/services/`, `src/forgeai/security.py`, `src/forgeai/tool_gateway.py`, and the deterministic/adversarial tests before changing risk or execution behavior.
