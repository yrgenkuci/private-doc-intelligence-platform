"""Unit tests for extraction base classes and interfaces.

Tests cover:
- Abstract base class enforcement
- ExtractionResult model validation
- Type safety and interface contracts
"""

import pytest

from services.extraction.base import ExtractionProvider, ExtractionResult
from services.extraction.schema import InvoiceData
from services.shared.config import Settings


def test_extraction_result_with_success() -> None:
    """Test ExtractionResult with successful extraction."""
    invoice_data = InvoiceData(invoice_number="INV-001", currency="USD")

    result = ExtractionResult(invoice_data=invoice_data, success=True, error=None, provider="test")

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-001"
    assert result.error is None
    assert result.provider == "test"


def test_extraction_result_with_failure() -> None:
    """Test ExtractionResult with failed extraction."""
    result = ExtractionResult(invoice_data=None, success=False, error="Test error", provider="test")

    assert result.success is False
    assert result.invoice_data is None
    assert result.error == "Test error"
    assert result.provider == "test"


def test_extraction_provider_is_abstract() -> None:
    """Test that ExtractionProvider cannot be instantiated directly."""
    settings = Settings()

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        ExtractionProvider(settings)  # type: ignore[abstract]


def test_extraction_provider_requires_implementation() -> None:
    """Test that concrete providers must implement all abstract methods."""

    # Create incomplete implementation missing provider_name
    class IncompleteProvider(ExtractionProvider):
        def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
            return ExtractionResult(
                invoice_data=None, success=False, error="Not implemented", provider="incomplete"
            )

        def is_available(self) -> bool:
            return True

        # Missing: provider_name property

    settings = Settings()

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteProvider(settings)  # type: ignore[abstract]


def test_concrete_provider_implementation() -> None:
    """Test that properly implemented provider works correctly."""

    class TestProvider(ExtractionProvider):
        def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
            return ExtractionResult(
                invoice_data=InvoiceData(invoice_number="TEST"),
                success=True,
                error=None,
                provider=self.provider_name,
            )

        def is_available(self) -> bool:
            return True

        @property
        def provider_name(self) -> str:
            return "test"

    settings = Settings()
    provider = TestProvider(settings)

    assert provider.provider_name == "test"
    assert provider.is_available() is True

    result = provider.extract_invoice_fields("Sample text")
    assert result.success is True
    assert result.provider == "test"
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "TEST"
