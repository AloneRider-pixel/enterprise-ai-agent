from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Gate(StrEnum):
    PASS = "pass"
    REVIEW_REQUIRED = "review_required"
    BLOCK = "block"


class Finding(BaseModel):
    severity: Severity
    category: str
    title: str
    detail: str
    paths: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    pull_request: int = Field(gt=0)


class RiskFactor(BaseModel):
    name: str
    points: int
    rationale: str


class ReviewReport(BaseModel):
    repository: str
    pull_request: int
    risk_score: int = Field(ge=0, le=100)
    gate: Gate
    findings: list[Finding] = Field(default_factory=list)
    factors: list[RiskFactor] = Field(default_factory=list)
    changed_files: int = Field(ge=0)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
