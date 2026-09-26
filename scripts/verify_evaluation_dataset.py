"""Validate the checked-in RAG evaluation dataset before it is used for evidence.

This script deliberately validates provenance inputs, not model quality. A green
check here proves that the evaluation corpus is structurally valid and stable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "eval_dataset.json"

required = {"question", "ground_truth", "context", "category"}
payload = json.loads(DATASET.read_text(encoding="utf-8"))

if not isinstance(payload, list) or not payload:
    raise SystemExit("Evaluation dataset must be a non-empty JSON array.")

questions: set[str] = set()
for index, case in enumerate(payload, start=1):
    if not isinstance(case, dict):
        raise SystemExit(f"Case {index} must be an object.")
    missing = required - case.keys()
    if missing:
        raise SystemExit(f"Case {index} is missing: {', '.join(sorted(missing))}")
    question = str(case["question"]).strip()
    if not question:
        raise SystemExit(f"Case {index} has an empty question.")
    if question in questions:
        raise SystemExit(f"Duplicate evaluation question at case {index}: {question}")
    questions.add(question)
    for field in ("ground_truth", "context", "category"):
        if not str(case[field]).strip():
            raise SystemExit(f"Case {index} has an empty {field}.")

digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()
categories = sorted({str(case["category"]) for case in payload})
print(
    f"evaluation corpus verified: cases={len(payload)}, "
    f"categories={len(categories)}, sha256={digest}"
)
