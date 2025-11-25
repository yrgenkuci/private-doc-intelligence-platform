"""Unit tests for configuration management."""

import os
from collections.abc import Generator

import pytest

from services.shared.config import Settings, get_settings


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Clean environment variables before and after test."""
    original_env = dict(os.environ)
    env_vars = [k for k in os.environ if k.startswith("APP_")]
    for var in env_vars:
        del os.environ[var]
    yield
    os.environ.clear()
    os.environ.update(original_env)


def test_settings_defaults(clean_env: None) -> None:
    """Test that settings have correct default values."""
    settings = Settings()

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.service_name == "doc-intelligence-platform"
    assert settings.service_version == "0.1.0"


def test_settings_from_env_vars(clean_env: None) -> None:
    """Test that settings can be overridden via environment variables."""
    os.environ["APP_ENVIRONMENT"] = "production"
    os.environ["APP_LOG_LEVEL"] = "ERROR"
    os.environ["APP_SERVICE_NAME"] = "test-service"

    settings = Settings()

    assert settings.environment == "production"
    assert settings.log_level == "ERROR"
    assert settings.service_name == "test-service"


def test_settings_case_insensitive(clean_env: None) -> None:
    """Test that environment variables are case insensitive."""
    os.environ["app_log_level"] = "DEBUG"

    settings = Settings()

    assert settings.log_level == "DEBUG"


def test_get_settings_factory() -> None:
    """Test that factory function returns Settings instance."""
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.service_name == "doc-intelligence-platform"
