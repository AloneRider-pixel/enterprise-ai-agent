"""Pydantic API schemas for validated request and response contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(min_length=1, max_length=200)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


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
    chunk_count: int
    created_at: datetime
    indexed_at: datetime | None = None


class DocumentListItem(BaseModel):
    documents: list[DocumentStatus] = Field(default_factory=list)
    total: int


class EvalMetric(str, Enum):
    FAITHFULNESS = "faithfulness"
    ANSWER_RELEVANCE = "answer_relevance"
    CONTEXT_RECALL = "context_recall"
    CONTEXT_PRECISION = "context_precision"


class EvalRequest(BaseModel):
    dataset_name: str = Field(default="default", min_length=1, max_length=128)
    metrics: list[EvalMetric] = Field(
        default_factory=lambda: [
            EvalMetric.FAITHFULNESS,
            EvalMetric.ANSWER_RELEVANCE,
            EvalMetric.CONTEXT_RECALL,
        ]
    )


class EvalResult(BaseModel):
    dataset_name: str
    metrics: dict[str, float] = Field(default_factory=dict)
    num_samples: int
    latency_stats: dict[str, float] = Field(default_factory=dict)
    cost_usd: float
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
