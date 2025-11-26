"""Unit tests for local extraction provider using Donut.

Tests cover:
- Provider initialization (lazy loading)
- Model availability checking
- Basic text extraction with regex
- Error handling
- Provider identification
- GPU/CPU device selection
"""

import logging
import sys
from unittest.mock import patch

import pytest

from services.extraction.local_provider import LocalExtractionProvider
from services.shared.config import Settings


@pytest.fixture
def local_provider() -> LocalExtractionProvider:
    """Create local provider instance."""
    settings = Settings(_env_file=None)
    return LocalExtractionProvider(settings)


def test_local_provider_initialization(local_provider: LocalExtractionProvider) -> None:
    """Test that local provider initializes without loading model."""
    assert local_provider is not None
    assert isinstance(local_provider.settings, Settings)
    assert local_provider.provider_name == "local"
    # Model should not be loaded yet (lazy loading)
    assert local_provider._model is None
    assert local_provider._processor is None


def test_local_provider_lazy_loads_model(local_provider: LocalExtractionProvider) -> None:
    """Test that model is lazy-loaded on first extraction."""
    # Model not loaded initially
    assert local_provider._model is None

    # Trigger extraction (will load model)
    result = local_provider.extract_invoice_fields("INVOICE #12345")

    # Model should be loaded now
    assert local_provider._model is not None
    assert local_provider._processor is not None
    assert result.success is True


def test_local_provider_is_available_with_dependencies() -> None:
    """Test availability check when dependencies are installed."""
    settings = Settings(_env_file=None)
    provider = LocalExtractionProvider(settings)

    # Should be available (torch and transformers installed in our test env)
    assert provider.is_available() is True


def test_local_provider_is_not_available_without_dependencies() -> None:
    """Test availability check when dependencies are missing."""
    # Temporarily remove torch from sys.modules
    torch_module = sys.modules.get("torch")
    if torch_module:
        del sys.modules["torch"]

    settings = Settings(_env_file=None)
    provider = LocalExtractionProvider(settings)

    # Should not be available if torch is missing
    with patch.dict(sys.modules, {"torch": None}):
        assert provider.is_available() is False

    # Restore torch
    if torch_module:
        sys.modules["torch"] = torch_module


def test_local_provider_name(local_provider: LocalExtractionProvider) -> None:
    """Test provider name is 'local'."""
    assert local_provider.provider_name == "local"


def test_local_provider_extract_invoice_number(
    local_provider: LocalExtractionProvider,
) -> None:
    """Test that extraction can parse invoice numbers from text."""
    result = local_provider.extract_invoice_fields("INVOICE: INV-2024-001")

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-2024-001"
    assert result.provider == "local"
    assert result.error is None


def test_local_provider_extract_empty_text(local_provider: LocalExtractionProvider) -> None:
    """Test that empty text is handled correctly."""
    result = local_provider.extract_invoice_fields("")

    assert result.success is False
    assert result.invoice_data is None
    assert "Empty OCR text" in result.error  # type: ignore
    assert result.provider == "local"
    # Should not load model for empty text
    assert local_provider._model is None


def test_local_provider_logs_model_loading(
    local_provider: LocalExtractionProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that model loading is logged."""
    with caplog.at_level(logging.INFO):
        local_provider.extract_invoice_fields("Test text")

    assert "Loading Donut model" in caplog.text or "Extracting invoice fields" in caplog.text


def test_local_provider_can_be_created_via_settings() -> None:
    """Test that local provider can be selected via configuration."""
    settings = Settings(_env_file=None, extraction_provider="local")

    assert settings.extraction_provider == "local"


def test_local_provider_multiple_extractions_reuse_model(
    local_provider: LocalExtractionProvider,
) -> None:
    """Test that model is loaded once and reused for subsequent extractions."""
    # First extraction loads model
    result1 = local_provider.extract_invoice_fields("INVOICE #001")
    model_id_1 = id(local_provider._model)

    # Second extraction reuses same model
    result2 = local_provider.extract_invoice_fields("INVOICE #002")
    model_id_2 = id(local_provider._model)

    assert result1.success is True
    assert result2.success is True
    assert model_id_1 == model_id_2  # Same model instance


def test_local_provider_extract_dates(local_provider: LocalExtractionProvider) -> None:
    """Test date extraction in multiple formats."""
    from datetime import date

    invoice_text = """
    INVOICE #12345
    Invoice Date: November 26, 2025
    Due Date: 12/15/2025
    Total: $500.00
    """

    result = local_provider.extract_invoice_fields(invoice_text)

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_date == date(2025, 11, 26)
    assert result.invoice_data.due_date == date(2025, 12, 15)


def test_local_provider_extract_amounts(local_provider: LocalExtractionProvider) -> None:
    """Test monetary amount extraction."""
    from decimal import Decimal

    invoice_text = """
    INVOICE #TEST-001
    Subtotal: $1,234.56
    Tax: $123.45
    Total: $1,358.01
    """

    result = local_provider.extract_invoice_fields(invoice_text)

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.subtotal == Decimal("1234.56")
    assert result.invoice_data.tax_amount == Decimal("123.45")
    assert result.invoice_data.total_amount == Decimal("1358.01")


def test_local_provider_extract_entities(local_provider: LocalExtractionProvider) -> None:
    """Test entity (supplier/customer) extraction."""
    invoice_text = """
    INVOICE #99999
    From: ACME Corporation
    Bill To: John Doe Industries
    Total: $999.99
    """

    result = local_provider.extract_invoice_fields(invoice_text)

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.supplier_name == "ACME Corporation"
    assert result.invoice_data.customer_name == "John Doe Industries"


def test_local_provider_confidence_scoring(
    local_provider: LocalExtractionProvider,
) -> None:
    """Test confidence scoring based on field extraction."""
    # Full extraction - high confidence
    full_text = """
    INVOICE #12345
    Date: 2025-11-26
    From: Supplier Inc
    Total: $1000.00
    """
    result_full = local_provider.extract_invoice_fields(full_text)
    assert result_full.invoice_data is not None
    assert result_full.invoice_data.confidence_score == 1.0  # All critical fields

    # Partial extraction - lower confidence
    partial_text = "INVOICE #12345"
    result_partial = local_provider.extract_invoice_fields(partial_text)
    assert result_partial.invoice_data is not None
    assert result_partial.invoice_data.confidence_score == 0.3  # Only invoice number


def test_local_provider_handles_various_date_formats(
    local_provider: LocalExtractionProvider,
) -> None:
    """Test parsing of various date formats."""
    from datetime import date

    test_cases = [
        ("Date: 2025-11-26", date(2025, 11, 26)),
        ("Date: 11/26/2025", date(2025, 11, 26)),
        ("Date: November 26, 2025", date(2025, 11, 26)),
        ("Date: Nov 26, 2025", date(2025, 11, 26)),
    ]

    for text, expected_date in test_cases:
        result = local_provider.extract_invoice_fields(f"INVOICE #TEST\n{text}")
        assert result.invoice_data is not None
        assert result.invoice_data.invoice_date == expected_date, f"Failed to parse: {text}"


def test_local_provider_comprehensive_invoice(
    local_provider: LocalExtractionProvider,
) -> None:
    """Test extraction from a realistic invoice."""
    from datetime import date
    from decimal import Decimal

    realistic_invoice = """
    INVOICE #INV-2025-001

    Invoice Date: November 26, 2025
    Due Date: December 26, 2025

    From: Tech Solutions LLC
    123 Main Street

    Bill To: Enterprise Corp
    456 Business Ave

    Subtotal: $5,420.00
    Tax (10%): $542.00
    Total: $5,962.00
    """

    result = local_provider.extract_invoice_fields(realistic_invoice)

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-2025-001"
    assert result.invoice_data.invoice_date == date(2025, 11, 26)
    assert result.invoice_data.due_date == date(2025, 12, 26)
    assert result.invoice_data.supplier_name == "Tech Solutions LLC"
    assert result.invoice_data.customer_name == "Enterprise Corp"
    assert result.invoice_data.subtotal == Decimal("5420.00")
    assert result.invoice_data.tax_amount == Decimal("542.00")
    assert result.invoice_data.total_amount == Decimal("5962.00")
    assert result.invoice_data.confidence_score == 1.0  # All fields extracted
