# ForgeAI — Embedded Review Core

This directory contains the ForgeAI implementation embedded in the Enterprise AI Agent repository. It provides deterministic pull-request risk analysis without granting analysis code implicit execution authority.

## Purpose

ForgeAI converts GitHub pull-request changes into structured, explainable engineering review signals:

```text
GitHub PR
   ↓
Change analysis
   ├── security-sensitive paths
   ├── dependency changes
   ├── test impact
   └── secret-like patterns
   ↓
Risk rules
   ↓
Typed review result
   ↓
Optional approval-gated automation
```

## Boundary

Repository content, diff text, logs, dependency metadata, and model output are untrusted. The review layer is bounded and deterministic where policy decisions are involved; side effects remain behind explicit authorization and approval controls owned by the surrounding application.

## Development

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn forgeai.main:app --reload
```

The parent repository owns environment configuration. Do not introduce credentials or duplicate secret configuration inside this directory.

## Verification

```bash
ruff check src tests scripts migrations
pytest
alembic upgrade head
python scripts/run_eval.py
python scripts/run_security_eval.py
python scripts/verify_evidence.py --help
```

These checks align with the security and quality controls represented by the parent repository.

## Review path

Start with `src/forgeai/security.py`, `src/forgeai/tool_gateway.py`, `src/forgeai/services/`, migration files, and deterministic/adversarial tests before changing risk rules or GitHub/tool integrations.

## Security

Never execute arbitrary repository content during analysis. Preserve webhook verification, input bounding, secret redaction, deterministic policy checks, and approval gates.

## License

MIT
