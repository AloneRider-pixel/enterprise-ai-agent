# Evidence and reproducibility policy

Enterprise AI Agent separates implemented capabilities, design targets, deterministic fixtures, and measured benchmark claims.

## Claim classes

- **Implemented**: supported by code, tests, configuration, or repository behavior.
- **Design target**: an engineering objective, not an observed result.
- **Deterministic fixture**: a controlled test input used to validate behavior, not a production benchmark.
- **Measured**: an observed result that must be reproducible and independently traceable.

## Rules for measured claims

A measured claim must identify:
1. Dataset or fixture version and a checksum when the input is file-backed.
2. Environment details such as Python/Node versions and relevant model/configuration versions.
3. Sample count, metric definition, and scoring method.
4. Timestamp and commit SHA.
5. The generated artifact or raw output used to derive the result.

Until those fields are present, performance numbers in this repository are treated as design targets rather than measured production results.

## AI-specific disclosure

LLM responses can vary across model versions and providers. Deterministic fixtures may verify control-flow behavior, schema validation, or citation wiring without establishing general model quality.

Claims about faithfulness, relevance, hallucination rate, latency, cost, or retrieval quality require an explicit evaluation record. Synthetic fixtures must not be presented as real-world model performance.

## Review standard

Changes to README metrics or evaluation outputs should update `evidence/claims.json`. CI validates the machine-readable policy record so unsupported measured entries cannot be added without provenance fields.
