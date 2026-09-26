# Verification guide

Run these checks from the repository root:

```bash
python scripts/verify_evidence.py
cd backend
python -m pip install -r requirements.txt
python -m pip check
python -m ruff check app/
python -m pytest tests/ -v --cov=app --cov-report=term-missing
cd ../frontend
npm install
npm run build
```

For container verification:

```bash
docker build -t enterprise-ai-agent-backend:verify ./backend
docker build -t enterprise-ai-agent-frontend:verify ./frontend
```

A green CI run proves that the declared repository checks passed for that commit. It does not prove production latency, model quality, availability, or business impact. Those require separately reproducible evaluation evidence.
