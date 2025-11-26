"""Unit tests for extraction provider factory.

Tests cover:
- Provider registry lookups
- Factory function provider creation
- Configuration-based selection
- Error handling for unknown providers
"""

import logging

import pytest

from services.extraction.base import ExtractionProvider
from services.extraction.factory import ProviderRegistry, create_extraction_service
from services.extraction.openai_provider import OpenAIExtractionProvider
from services.shared.config import Settings


def test_provider_registry_default_providers() -> None:
    """Test that registry contains default providers."""
    providers = ProviderRegistry.list_providers()

    assert "openai" in providers
    assert len(providers) >= 1


def test_provider_registry_get_openai() -> None:
    """Test getting OpenAI provider from registry."""
    provider_class = ProviderRegistry.get_provider_class("openai")

    assert provider_class == OpenAIExtractionProvider


def test_provider_registry_unknown_provider() -> None:
    """Test that unknown provider raises ValueError."""
    with pytest.raises(ValueError, match="Unknown extraction provider"):
        ProviderRegistry.get_provider_class("nonexistent")


def test_provider_registry_error_message_lists_available() -> None:
    """Test that error message lists available providers."""
    try:
        ProviderRegistry.get_provider_class("invalid")
    except ValueError as e:
        error_msg = str(e)
        assert "Available providers" in error_msg
        assert "openai" in error_msg


def test_provider_registry_register_new_provider() -> None:
    """Test registering a new provider."""

    class TestProvider(ExtractionProvider):
        def extract_invoice_fields(self, ocr_text: str):  # type: ignore
            pass

        def is_available(self) -> bool:
            return True

        @property
        def provider_name(self) -> str:
            return "test"

    # Register
    ProviderRegistry.register("test", TestProvider)

    # Verify registered
    assert "test" in ProviderRegistry.list_providers()
    assert ProviderRegistry.get_provider_class("test") == TestProvider

    # Clean up
    del ProviderRegistry._providers["test"]


def test_create_extraction_service_default() -> None:
    """Test factory creates OpenAI provider by default."""
    settings = Settings(_env_file=None)
    provider = create_extraction_service(settings)

    assert isinstance(provider, OpenAIExtractionProvider)
    assert provider.provider_name == "openai"


def test_create_extraction_service_logs_creation(caplog: pytest.LogCaptureFixture) -> None:
    """Test that factory logs provider creation."""
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.INFO):
        create_extraction_service(settings)

    assert "Created extraction provider: openai" in caplog.text


def test_create_extraction_service_warns_if_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that factory warns if provider is not available."""
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.WARNING):
        provider = create_extraction_service(settings)
        # OpenAI provider won't be available without API key

    if not provider.is_available():
        assert "not fully available" in caplog.text


def test_create_extraction_service_with_invalid_provider() -> None:
    """Test that factory raises error for invalid provider in settings."""
    # This test verifies the Settings validation, not the factory
    # Invalid provider should be caught by Pydantic before reaching factory
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, extraction_provider="invalid")  # type: ignore
