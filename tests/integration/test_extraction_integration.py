"""Integration tests for LLM extraction service.

These tests require:
- OPENAI_API_KEY environment variable set
- Internet connection to OpenAI API

Tests are skipped if OPENAI_API_KEY is not available.
Use pytest -v -m integration to run only integration tests.
"""

import os

import pytest

from services.extraction.service import ExtractionService
from services.shared.config import Settings

# Skip all tests in this module if no API key available
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping integration tests",
)


@pytest.fixture
def settings() -> Settings:
    """Create settings for integration tests."""
    return Settings()


@pytest.fixture
def extraction_service(settings: Settings) -> ExtractionService:
    """Create extraction service for integration tests."""
    return ExtractionService(settings)


def test_extract_invoice_from_real_text(extraction_service: ExtractionService) -> None:
    """Test extraction with realistic invoice text."""
    # Sample invoice text similar to what OCR would produce
    invoice_text = """
    INVOICE

    Invoice Number: INV-2024-001
    Date: January 15, 2024
    Due Date: February 15, 2024

    Bill To:
    ABC Corporation
    123 Main Street
    New York, NY 10001

    From:
    XYZ Suppliers Inc.
    456 Oak Avenue
    Los Angeles, CA 90001

    Description                  Quantity    Price      Total
    Office Supplies                  10      $50.00    $500.00
    Computer Equipment                5     $100.00    $500.00

    Subtotal:                                        $1,000.00
    Tax (10%):                                         $100.00
    Total Amount Due:                                $1,100.00

    Payment Terms: Net 30
    Currency: USD
    """

    result = extraction_service.extract_invoice_fields(invoice_text)

    # Verify extraction succeeded
    assert result.success is True
    assert result.error is None
    assert result.invoice_data is not None

    # Verify key fields were extracted
    invoice_data = result.invoice_data
    assert invoice_data.invoice_number is not None
    assert "INV-2024-001" in invoice_data.invoice_number or "2024" in invoice_data.invoice_number

    # Verify financial amounts
    assert invoice_data.total_amount is not None
    assert float(invoice_data.total_amount) > 0

    # Verify currency
    assert invoice_data.currency is not None
    assert invoice_data.currency == "USD"


def test_extract_invoice_with_minimal_data(extraction_service: ExtractionService) -> None:
    """Test extraction with minimal invoice information."""
    minimal_text = """
    Invoice #12345
    Amount: $250.00
    """

    result = extraction_service.extract_invoice_fields(minimal_text)

    # Should still succeed, but with fewer fields populated
    assert result.success is True
    assert result.invoice_data is not None
    assert (
        result.invoice_data.invoice_number is not None
        or result.invoice_data.total_amount is not None
    )


def test_extract_invoice_with_empty_text(extraction_service: ExtractionService) -> None:
    """Test extraction with empty text (should fail gracefully)."""
    result = extraction_service.extract_invoice_fields("")

    # Should fail gracefully with clear error
    assert result.success is False
    assert result.error is not None
    assert "empty" in result.error.lower()
    assert result.invoice_data is None


def test_extract_invoice_with_non_invoice_text(extraction_service: ExtractionService) -> None:
    """Test extraction with text that doesn't contain invoice data."""
    non_invoice_text = """
    This is just a random paragraph of text.
    It contains no invoice information at all.
    Just some sentences about various topics.
    """

    result = extraction_service.extract_invoice_fields(non_invoice_text)

    # Should succeed but return mostly null fields
    assert result.success is True
    assert result.invoice_data is not None
    # Most fields should be None since no invoice data present
    invoice_data = result.invoice_data
    null_count = sum(
        1
        for field in [
            invoice_data.invoice_number,
            invoice_data.invoice_date,
            invoice_data.due_date,
            invoice_data.supplier_name,
            invoice_data.customer_name,
            invoice_data.total_amount,
        ]
        if field is None
    )
    # Expect most fields to be None
    assert null_count >= 4


def test_extract_invoice_with_european_format(extraction_service: ExtractionService) -> None:
    """Test extraction with European invoice format."""
    european_invoice = """
    RECHNUNG / INVOICE

    Rechnungsnummer: RE-2024-042
    Datum: 15.01.2024
    Fälligkeitsdatum: 15.02.2024

    Lieferant: Müller GmbH
    Kunde: Schmidt AG

    Gesamtbetrag: 1.500,00 EUR
    MwSt (19%): 285,00 EUR
    Endbetrag: 1.785,00 EUR
    """

    result = extraction_service.extract_invoice_fields(european_invoice)

    # Should handle European format
    assert result.success is True
    assert result.invoice_data is not None

    invoice_data = result.invoice_data
    # Should extract invoice number
    assert invoice_data.invoice_number is not None

    # Should recognize EUR currency
    if invoice_data.currency:
        assert invoice_data.currency == "EUR"


@pytest.mark.slow
def test_extract_invoice_performance(extraction_service: ExtractionService) -> None:
    """Test that extraction completes in reasonable time."""
    import time

    invoice_text = """
    Invoice #TEST-001
    Date: 2024-01-15
    Amount: $100.00
    """

    start_time = time.time()
    result = extraction_service.extract_invoice_fields(invoice_text)
    duration = time.time() - start_time

    # Should complete within 10 seconds (API call)
    assert duration < 10.0
    assert result.success is True


def test_extract_invoice_retry_logic() -> None:
    """Test that retry logic is configured (unit test, doesn't call API)."""
    # This just verifies the retry decorator is present
    from services.extraction.service import ExtractionService

    # Check that the retry method exists
    assert hasattr(ExtractionService, "_call_openai_with_retry")

    # Check that it has retry configuration
    method = ExtractionService._call_openai_with_retry
    assert hasattr(method, "retry")
