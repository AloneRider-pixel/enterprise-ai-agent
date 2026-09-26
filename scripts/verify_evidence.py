#!/usr/bin/env python3
"""Validate the machine-readable evidence policy without inventing results."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS_PATH = ROOT / "evidence" / "claims.json"
ALLOWED_CLASSES = {'implemented', 'design_target', 'deterministic_fixture', 'measured'}
ALLOWED_STATUSES = {'verified', 'not_measured', 'pending_review'}

def main() -> int:
    data = json.loads(CLAIMS_PATH.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise SystemExit('Unsupported evidence schema version')
    claims = data.get('claims')
    if not isinstance(claims, list) or not claims:
        raise SystemExit('claims must be a non-empty list')
    ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise SystemExit('Each claim must be an object')
        claim_id = claim.get('id')
        if not isinstance(claim_id, str) or not claim_id:
            raise SystemExit('Each claim needs a non-empty id')
        if claim_id in ids:
            raise SystemExit(f'Duplicate claim id: {claim_id}')
        ids.add(claim_id)
        claim_class = claim.get('class')
        status = claim.get('status')
        if claim_class not in ALLOWED_CLASSES:
            raise SystemExit(f'{claim_id}: invalid class {claim_class!r}')
        if status not in ALLOWED_STATUSES:
            raise SystemExit(f'{claim_id}: invalid status {status!r}')
        if claim_class == 'measured':
            required = {'dataset','environment','sample_count','metric','timestamp','commit','artifact'}
            missing = sorted(required - claim.keys())
            if missing:
                raise SystemExit(f"{claim_id}: measured claim missing {', '.join(missing)}")
            artifact = ROOT / str(claim['artifact'])
            if not artifact.is_file():
                raise SystemExit(f"{claim_id}: evidence artifact does not exist: {claim['artifact']}")
    print(f'Evidence policy valid: {len(claims)} claims checked.')
    print('No measured production-result claims are declared without provenance.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
