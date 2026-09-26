"""Pydantic schemas for the public API contract."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    size_bytes: int
    status: str
    created_at: datetime


class DocumentStatus(BaseModel):
    document_id: str
    filename: str
    status: str
    chunk_count: int = 0
    created_at: datetime
    indexed_at: datetime | None = None


class DocumentListItem(BaseModel):
    documents: list[DocumentStatus]
    total: int


class ChatMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=12000)
    stream: bool = False


class ChatResponse(BaseModel):
    session_id: str
    message: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationHistory(BaseModel):
    session_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationMetric(str, Enum):
    faithfulness = "faithfulness"
    answer_relevance = "answer_relevance"
    context_recall = "context_recall"
    context_precision = "context_precision"


class EvalRequest(BaseModel):
    dataset_name: str = Field(default="default", min_length=1, max_length=255)
    metrics: list[EvaluationMetric] = Field(
        default_factory=lambda: [
            EvaluationMetric.faithfulness,
            EvaluationMetric.answer_relevance,
            EvaluationMetric.context_recall,
        ]
    )


class EvalResult(BaseModel):
    dataset_name: str
    metrics: dict[str, float] = Field(default_factory=dict)
    num_samples: int
    latency_stats: dict[str, float | int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    timestamp: datetime


class SystemMetrics(BaseModel):
    total_documents: int
    total_chunks: int
    total_queries: int
    avg_latency_ms: float
    total_cost_usd: float
    active_sessions: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    openai: str
