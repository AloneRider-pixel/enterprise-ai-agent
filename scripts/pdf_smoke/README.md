# PDF UI smoke test (offline fixture)

This verifies upload, OCR, real database retrieval, source identity, and page-image opening. Chat responses are a context-checked fixture; embeddings are deterministic hashing vectors. Neither proves OpenAI model quality. No paid APIs are called.

Requires Python 3.10, PostgreSQL 14 + pgvector >=0.5, Node, Google Chrome, and Tesseract. Install backend requirements in a fresh virtual environment, plus `pip install playwright`; install the frontend with `npm ci` in `frontend`.

1. Create a **disposable** database `enterprise_pdf_smoke` on localhost port 5433 with user `test_user` and password `test_password` (the checked-in fixture defaults). Do not point this fixture at user data. `PDF_SMOKE_DB` overrides that database name.
2. From the repo root, run `python scripts/pdf_smoke/make_pdf.py`.
3. Run `cd backend && PYTHONPATH=. python ../scripts/pdf_smoke/server.py`.
4. In another terminal, run `cd frontend && npx vite --config vite.config.e2e.js --port 3000`.
5. Run `python scripts/pdf_smoke/ui_test.py` from the repo root.

Outputs go to `/tmp/enterprise-pdf-smoke` (`PDF_SMOKE_DIR` overrides). Assertions check both pricing facts, screenshot-only text reaching the generation prompt, and that a source opens. Screenshots are generated for manual visual inspection. Reset the disposable database between runs because the upload is deduplicated. Stop the two servers when finished.

The standalone database regression is opt-in: `RUN_DB_TESTS=1 PYTHONPATH=. pytest tests/test_database_roundtrip.py` from `backend`, using the configured **test database**. It inserts and removes only its own temporary document.
