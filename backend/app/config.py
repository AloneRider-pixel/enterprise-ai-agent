"""
Application configuration using pydantic-settings.
All settings loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─── Application ───
    app_name: str = Field(default="enterprise-ai-agent", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    secret_key: str = Field(default="dev-secret-change-me", alias="SECRET_KEY")

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
    redis_password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # ─── Authentication ───
    jwt_secret_key: str = Field(default="jwt-dev-secret", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ─── Rate Limiting ───
    rate_limit_requests: int = Field(default=60, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    # ─── RAG Configuration ───
    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=64)
    retrieval_top_k: int = Field(default=10)
    rerank_top_n: int = Field(default=4)
    similarity_threshold: float = Field(default=0.7)

    # ─── Hallucination Detection ───
    hallucination_threshold: float = Field(default=0.7, alias="HALLUCINATION_THRESHOLD")

    # ─── Cost Tracking ───
    cost_alert_threshold_usd: float = Field(default=10.0, alias="COST_ALERT_THRESHOLD_USD")

    # ─── Token Pricing (per 1K tokens) ───
    gpt4o_mini_input_price: float = 0.00015  # $0.15 per 1M tokens
    gpt4o_mini_output_price: float = 0.0006  # $0.60 per 1M tokens
    embedding_price: float = 0.00002  # $0.02 per 1M tokens

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
