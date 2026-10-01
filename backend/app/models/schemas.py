"""Pydantic request/response schemas for the Enterprise AI Agent API."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class ChatMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
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
    documents: list[DocumentStatus] = Field(default_factory=list)
    total: int


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    size_bytes: int
    status: str
    created_at: datetime


class EvaluationMetric(str, Enum):
    FAITHFULNESS = "faithfulness"
    ANSWER_RELEVANCE = "answer_relevance"
    CONTEXT_RECALL = "context_recall"
    CONTEXT_PRECISION = "context_precision"


class EvalRequest(BaseModel):
    dataset_name: str = Field(default="default", min_length=1, max_length=100)
    metrics: list[EvaluationMetric] = Field(
        default_factory=lambda: [
            EvaluationMetric.FAITHFULNESS,
            EvaluationMetric.ANSWER_RELEVANCE,
            EvaluationMetric.CONTEXT_RECALL,
        ]
    )


class EvalResult(BaseModel):
    dataset_name: str
    metrics: dict
    num_samples: int
    latency_stats: dict
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
