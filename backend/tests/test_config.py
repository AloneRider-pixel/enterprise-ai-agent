"""Configuration security regression tests."""
import pytest

from app.config import Settings


def test_production_rejects_debug():
    with pytest.raises(ValueError, match="DEBUG"):
        Settings(
            APP_ENV="production",
            DEBUG=True,
            SECRET_KEY="ci-secret",
            OPENAI_API_KEY="ci-openai",
            JWT_SECRET_KEY="ci-jwt",
        )


def test_production_rejects_default_database_password():
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            SECRET_KEY="ci-secret",
            OPENAI_API_KEY="ci-openai",
            JWT_SECRET_KEY="ci-jwt",
        )
