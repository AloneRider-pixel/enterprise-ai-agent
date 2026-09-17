from forgeai.models import Gate, RiskFactor
from forgeai.services.github_client import PullRequestSnapshot
from forgeai.services.risk import calculate_risk


def snapshot(files: int = 3, additions: int = 20, deletions: int = 5) -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="acme/api",
        number=1,
        title="test",
        body="",
        additions=additions,
        deletions=deletions,
        changed_files=files,
        filenames=[],
    )


def test_low_risk_passes() -> None:
    score, gate = calculate_risk(snapshot(), [], 70)
    assert score == 0
    assert gate == Gate.PASS


def test_security_and_test_risk_requires_review() -> None:
    factors = [
        RiskFactor(name="security_surface", points=30, rationale="security"),
        RiskFactor(name="test_impact", points=20, rationale="tests"),
        RiskFactor(name="dependency_change", points=10, rationale="deps"),
    ]
    score, gate = calculate_risk(snapshot(), factors, 50)
    assert score == 60
    assert gate == Gate.REVIEW_REQUIRED


def test_large_change_adds_bounded_risk() -> None:
    factors = [RiskFactor(name="security_surface", points=30, rationale="security")]
    score, gate = calculate_risk(
        snapshot(files=30, additions=800, deletions=300), factors, 70
    )
    assert score == 50
    assert gate == Gate.PASS
