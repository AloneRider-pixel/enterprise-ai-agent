from fastapi import FastAPI, HTTPException

from forgeai.config import settings
from forgeai.models import ReviewReport, ReviewRequest
from forgeai.services.analyzer import analyze
from forgeai.services.github_client import GitHubClient, GitHubClientError
from forgeai.services.risk import calculate_risk

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI software engineering review platform",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/v1/reviews", response_model=ReviewReport)
async def create_review(request: ReviewRequest) -> ReviewReport:
    client = GitHubClient(settings)
    try:
        snapshot = await client.get_pull_request(request.repository, request.pull_request)
    except GitHubClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    findings, factors = analyze(snapshot)
    risk_score, gate = calculate_risk(
        snapshot=snapshot,
        factors=factors,
        gate_threshold=settings.review_gate_threshold,
    )

    return ReviewReport(
        repository=snapshot.repository,
        pull_request=snapshot.number,
        risk_score=risk_score,
        gate=gate,
        findings=findings,
        factors=factors,
        changed_files=snapshot.changed_files,
        additions=snapshot.additions,
        deletions=snapshot.deletions,
    )
