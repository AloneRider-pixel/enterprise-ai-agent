# Verification & Evidence

This project follows an evidence-first policy for technical claims.

## Claim classes

- **Capability:** behavior implemented in source and covered by tests or documented execution.
- **Design target:** an engineering target, not a measured production result.
- **Measured benchmark:** a result tied to a fixed dataset, environment, commit, and command.
- **Synthetic/demo:** generated data used only to exercise workflows or UI paths.

## Current evidence

| Area | Evidence | Reproduction |
|---|---|---|
| Backend correctness | backend/tests/ | cd backend && python -m pytest tests/ -v |
| Static quality | Ruff CI job | GitHub Actions: Enterprise AI Agent CI |
| Container build | Docker CI job | docker build for backend and frontend |
| RAG evaluation | evaluation/eval_dataset.json and backend/app/evaluation/ | Run the evaluation harness in the configured test environment |
| Workflow security | .github/workflows/scorecard.yml | OpenSSF Scorecard workflow |
| Static security analysis | .github/workflows/codeql.yml | CodeQL workflow |

## Benchmark publication rule

A numeric result is publishable only when the repository records the dataset/scenario version, sample count, environment, exact command, application commit, and timestamp. Otherwise it remains a target, capability statement, or synthetic/demo result.

## Known limitations

The default RAG evaluation dataset is a curated local benchmark. It is useful for regression testing, but it is not evidence of production accuracy or general model performance.

The CI lint gate currently enforces blocking formatting/syntax-style errors (`E`) while legacy advisory rules remain outside the merge gate; tests, static security analysis, and dependency resolution remain blocking.