"""
Application configuration using pydantic-settings.
All settings loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─── Application ───
    app_name: str = Field(default="enterprise-ai-agent", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    secret_key: str = Field(alias="SECRET_KEY")
    cors_allowed_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ALLOWED_ORIGINS")

    # ─── OpenAI ───
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )
    openai_embedding_dimensions: int = Field(default=1536)

    # ─── PostgreSQL ───
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="enterprise_agent", alias="POSTGRES_DB")
    postgres_user: str = Field(default="agent_user", alias="POSTGRES_USER")
    postgres_password: str = Field(default="agent_password", alias="POSTGRES_PASSWORD")

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # ─── Redis ───
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str | None = Field(default=None, alias="REDIS_PASSWORD")

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # ─── Authentication ───
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ─── Rate Limiting ───
    rate_limit_requests: int = Field(default=60, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    # ─── Public-access controls (both optional; unset keeps current behaviour) ───
    # When set, POST /api/auth/register requires a matching X-Invite-Code header.
    registration_invite_code: str | None = Field(default=None, alias="REGISTRATION_INVITE_CODE")
    # When set (> 0), total model-call units per UTC day across all users. Fails closed.
    daily_model_call_cap: int | None = Field(default=None, alias="DAILY_MODEL_CALL_CAP")

    # ─── RAG Configuration ───
    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=64)
    retrieval_top_k: int = Field(default=10)
    rerank_top_n: int = Field(default=4)
    similarity_threshold: float = Field(default=0.7)

    # ─── Local ML models ───
    # On small hosts (e.g. 512 MB) loading torch cross-encoders exhausts memory.
    # When true, reranking and hallucination scoring use their built-in
    # heuristic fallbacks instead.
    disable_local_models: bool = Field(default=False, alias="DISABLE_LOCAL_MODELS")

    # ─── Hallucination Detection ───
    hallucination_threshold: float = Field(default=0.7, alias="HALLUCINATION_THRESHOLD")

    # ─── Cost Tracking ───
    cost_alert_threshold_usd: float = Field(default=10.0, alias="COST_ALERT_THRESHOLD_USD")

    # ─── Token Pricing (per 1K tokens) ───
    gpt4o_mini_input_price: float = 0.00015  # $0.15 per 1M tokens
    gpt4o_mini_output_price: float = 0.0006  # $0.60 per 1M tokens
    embedding_price: float = 0.00002  # $0.02 per 1M tokens

    @model_validator(mode="after")
    def validate_runtime_security(self):
        """Reject known insecure defaults in production-like environments."""
        if self.app_env.lower() in {"production", "prod"}:
            if self.debug:
                raise ValueError("DEBUG must be false in production.")
            if self.postgres_password == "agent_password":
                raise ValueError("POSTGRES_PASSWORD must be explicitly configured in production.")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
