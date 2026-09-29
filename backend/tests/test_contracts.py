import os

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models.schemas import (
    ChatMessage,
    EvalRequest,
    MetricName,
    UserRegister,
)


def test_user_registration_contract_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        UserRegister(
            email="test@example.com",
            password="short",
            full_name="Test User",
        )


def test_chat_contract_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(session_id="session", message="")


def test_evaluation_contract_has_explicit_metrics() -> None:
    request = EvalRequest()
    assert MetricName.faithfulness in request.metrics
    assert MetricName.answer_relevance in request.metrics


def test_production_settings_reject_default_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings()


def test_test_environment_can_use_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    settings = Settings()
    assert settings.app_env == "test"
    assert settings.jwt_secret_key == "jwt-dev-secret"
