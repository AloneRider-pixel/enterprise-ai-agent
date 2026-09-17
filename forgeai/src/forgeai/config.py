from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ForgeAI"
    github_token: str | None = None
    github_api_base: str = "https://api.github.com"
    review_gate_threshold: int = 70
    request_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FORGEAI_",
        extra="ignore",
    )


settings = Settings()
