from forgeai.models import Gate, RiskFactor
from forgeai.services.github_client import PullRequestSnapshot


def calculate_risk(
    snapshot: PullRequestSnapshot,
    factors: list[RiskFactor],
    gate_threshold: int,
) -> tuple[int, Gate]:
    score = sum(factor.points for factor in factors)

    if snapshot.changed_files >= 20:
        score += 10
    if snapshot.additions + snapshot.deletions >= 500:
        score += 10

    score = min(score, 100)

    security_surface = any(factor.name == "security_surface" for factor in factors)
    if security_surface and score >= 80:
        return score, Gate.BLOCK
    if score >= gate_threshold:
        return score, Gate.REVIEW_REQUIRED
    return score, Gate.PASS
