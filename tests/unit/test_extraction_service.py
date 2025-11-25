"""Unit tests for LLM extraction service.

Tests cover:
- Invoice schema validation
- Extraction service initialization
- Successful extraction with mocked API
- Error handling for various failure cases
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.extraction.schema import InvoiceData
from services.extraction.service import ExtractionResult, ExtractionService
from services.shared.config import Settings


@pytest.fixture
def extraction_service() -> ExtractionService:
    """Create extraction service instance."""
    settings = Settings()
    return ExtractionService(settings)


@pytest.fixture
def sample_invoice_data() -> dict[str, any]:
    """Sample invoice data for testing."""
    return {
        "invoice_number": "INV-12345",
        "invoice_date": "2024-01-15",
        "due_date": "2024-02-15",
        "supplier_name": "Acme Corp",
        "supplier_address": "123 Main St, City, State 12345",
        "customer_name": "Test Customer Inc",
        "subtotal": 1000.00,
        "tax_amount": 100.00,
        "total_amount": 1100.00,
        "currency": "USD",
        "confidence_score": 0.95,
    }


def test_invoice_data_model_valid() -> None:
    """Test InvoiceData model with valid data."""
    invoice = InvoiceData(
        invoice_number="INV-123",
        invoice_date=date(2024, 1, 15),
        total_amount=Decimal("1234.56"),
        currency="USD",
    )

    assert invoice.invoice_number == "INV-123"
    assert invoice.invoice_date == date(2024, 1, 15)
    assert invoice.total_amount == Decimal("1234.56")
    assert invoice.currency == "USD"


def test_invoice_data_model_all_none() -> None:
    """Test InvoiceData model with all None values."""
    invoice = InvoiceData()

    assert invoice.invoice_number is None
    assert invoice.invoice_date is None
    assert invoice.total_amount is None
    assert invoice.currency == "USD"  # Has default


def test_extraction_service_initialization(extraction_service: ExtractionService) -> None:
    """Test that extraction service initializes correctly."""
    assert extraction_service is not None
    assert isinstance(extraction_service.settings, Settings)


@patch.dict("os.environ", {}, clear=True)
def test_extract_without_api_key(extraction_service: ExtractionService) -> None:
    """Test extraction fails gracefully without API key."""
    result = extraction_service.extract_invoice_fields("Sample invoice text")

    assert result.success is False
    assert result.invoice_data is None
    assert "OPENAI_API_KEY" in result.error


def test_extract_empty_text(extraction_service: ExtractionService) -> None:
    """Test extraction handles empty text."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        result = extraction_service.extract_invoice_fields("")

        assert result.success is False
        assert result.invoice_data is None
        assert "Empty OCR text" in result.error


@patch("services.extraction.service.OpenAI")
@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
def test_extract_success(
    mock_openai_class: MagicMock,
    extraction_service: ExtractionService,
    sample_invoice_data: dict[str, any],
) -> None:
    """Test successful invoice data extraction."""
    # Mock OpenAI client and response
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.function_call = MagicMock()
    mock_response.choices[0].message.function_call.arguments = (
        '{"invoice_number": "INV-12345", "total_amount": 1100.00, '
        '"currency": "USD", "invoice_date": "2024-01-15"}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    ocr_text = "INVOICE #INV-12345\nDate: 2024-01-15\nTotal: $1,100.00"
    result = extraction_service.extract_invoice_fields(ocr_text)

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-12345"
    assert result.invoice_data.total_amount == Decimal("1100.00")
    assert result.error is None
    mock_client.chat.completions.create.assert_called_once()


@patch("services.extraction.service.OpenAI")
@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
def test_extract_api_error(
    mock_openai_class: MagicMock, extraction_service: ExtractionService
) -> None:
    """Test extraction handles API errors."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API connection failed")

    result = extraction_service.extract_invoice_fields("Test invoice")

    assert result.success is False
    assert result.invoice_data is None
    assert "Extraction failed" in result.error
    assert "API connection failed" in result.error


def test_extraction_result_model() -> None:
    """Test ExtractionResult model."""
    result = ExtractionResult(invoice_data=InvoiceData(invoice_number="TEST-123"), success=True)

    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "TEST-123"
    assert result.error is None


@patch("services.extraction.service.OpenAI")
@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
def test_extract_with_retry_on_transient_error(
    mock_openai_class: MagicMock, extraction_service: ExtractionService
) -> None:
    """Test extraction retries on transient errors and succeeds."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    # First call fails, second succeeds
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.function_call = MagicMock()
    mock_response.choices[
        0
    ].message.function_call.arguments = '{"invoice_number": "INV-RETRY", "total_amount": 500.00}'

    mock_client.chat.completions.create.side_effect = [
        Exception("Temporary API error"),  # First attempt fails
        mock_response,  # Second attempt succeeds
    ]

    ocr_text = "INVOICE #INV-RETRY\nTotal: $500.00"
    result = extraction_service.extract_invoice_fields(ocr_text)

    # Should succeed after retry
    assert result.success is True
    assert result.invoice_data is not None
    assert result.invoice_data.invoice_number == "INV-RETRY"
    assert mock_client.chat.completions.create.call_count == 2  # Retried once


@patch("services.extraction.service.OpenAI")
@patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
def test_extract_fails_after_max_retries(
    mock_openai_class: MagicMock, extraction_service: ExtractionService
) -> None:
    """Test extraction fails after exhausting all retries."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    # All attempts fail
    mock_client.chat.completions.create.side_effect = Exception("Persistent API error")

    ocr_text = "Test invoice"
    result = extraction_service.extract_invoice_fields(ocr_text)

    # Should fail after max retries
    assert result.success is False
    assert result.invoice_data is None
    assert "Extraction failed" in result.error
    assert "Persistent API error" in result.error
    assert mock_client.chat.completions.create.call_count == 3  # Max 3 attempts
