"""Unit tests for local extraction provider (stub).

Tests cover:
- Provider initialization
- Stub behavior (returns empty data)
- Availability checking
- Error handling
- Provider identification
"""

import logging

import pytest

from services.extraction.local_provider import LocalExtractionProvider
from services.shared.config import Settings


@pytest.fixture
def local_provider() -> LocalExtractionProvider:
    """Create local provider instance."""
    settings = Settings(_env_file=None)
    return LocalExtractionProvider(settings)


def test_local_provider_initialization(local_provider: LocalExtractionProvider) -> None:
    """Test that local provider initializes correctly."""
    assert local_provider is not None
    assert isinstance(local_provider.settings, Settings)
    assert local_provider.provider_name == "local"


def test_local_provider_is_available(local_provider: LocalExtractionProvider) -> None:
    """Test that local provider reports as available (stub mode)."""
    assert local_provider.is_available() is True


def test_local_provider_name(local_provider: LocalExtractionProvider) -> None:
    """Test provider name is 'local'."""
    assert local_provider.provider_name == "local"


def test_local_provider_logs_stub_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Test that initialization logs stub warning."""
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.WARNING):
        LocalExtractionProvider(settings)

    assert "STUB implementation" in caplog.text


def test_local_provider_extract_returns_empty_data(
    local_provider: LocalExtractionProvider,
) -> None:
    """Test that stub extraction returns empty invoice data."""
    result = local_provider.extract_invoice_fields("Sample invoice text")

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number is None
    assert result.invoice_data.total_amount is None
    assert result.provider == "local"
    assert result.error is None


def test_local_provider_extract_empty_text(local_provider: LocalExtractionProvider) -> None:
    """Test that empty text is handled correctly."""
    result = local_provider.extract_invoice_fields("")

    assert result.success is False
    assert result.invoice_data is None
    assert "Empty OCR text" in result.error  # type: ignore
    assert result.provider == "local"


def test_local_provider_extract_logs_stub_usage(
    local_provider: LocalExtractionProvider, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that extraction logs stub usage."""
    with caplog.at_level(logging.INFO):
        local_provider.extract_invoice_fields("Test text")

    assert "STUB local extraction" in caplog.text


def test_local_provider_can_be_created_via_settings() -> None:
    """Test that local provider can be selected via configuration."""
    settings = Settings(_env_file=None, extraction_provider="local")

    assert settings.extraction_provider == "local"
