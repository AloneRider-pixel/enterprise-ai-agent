"""Pydantic API contracts used by the enterprise agent."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(gt=0)


class ChatMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20000)
    stream: bool = False


class ChatResponse(BaseModel):
    session_id: str
    message: str
    citations: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ConversationHistory(BaseModel):
    session_id: str
    messages: list[dict] = Field(default_factory=list)


class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    status: str
    chunk_count: int
    created_at: datetime
    indexed_at: datetime | None = None


class DocumentListItem(BaseModel):
    documents: list[DocumentStatus]
    total: int = Field(ge=0)


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    size_bytes: int = Field(ge=0)
    status: str
    created_at: datetime


class MetricName(str, Enum):
    faithfulness = "faithfulness"
    answer_relevance = "answer_relevance"
    context_recall = "context_recall"
    context_precision = "context_precision"


class EvalRequest(BaseModel):
    dataset_name: str = Field(default="default", min_length=1, max_length=255)
    metrics: list[MetricName] = Field(
        default_factory=lambda: [
            MetricName.faithfulness,
            MetricName.answer_relevance,
            MetricName.context_recall,
        ]
    )


class EvalResult(BaseModel):
    dataset_name: str
    metrics: dict[str, float]
    num_samples: int = Field(ge=0)
    latency_stats: dict[str, float | int] = Field(default_factory=dict)
    cost_usd: float = Field(ge=0)
    timestamp: datetime


class SystemMetrics(BaseModel):
    total_documents: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    total_queries: int = Field(ge=0)
    avg_latency_ms: float = Field(ge=0)
    total_cost_usd: float = Field(ge=0)
    active_sessions: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    openai: str
