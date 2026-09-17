# Security Policy

## Scope

ForgeAI handles GitHub pull-request metadata and is designed to inspect source-code changes. Never place production secrets in issues, fixtures, or example payloads.

## Design principles

- GitHub tokens are supplied through environment variables.
- The v0.1 analyzer is read-only with respect to GitHub.
- Findings and risk scores are deterministic and explainable.
- Future agent tools must be explicitly allowlisted and permissioned.
