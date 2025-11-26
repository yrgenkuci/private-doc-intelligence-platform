"""Unit tests for document ingestion API.

Tests cover:
- Health check endpoints
- File upload validation
- OCR integration
- Prometheus metrics endpoint
"""

import io
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image

from services.api.main import app
from services.extraction.base import ExtractionResult
from services.extraction.schema import InvoiceData
from services.ocr.service import OCRResult


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create a simple test image as bytes."""
    img = Image.new("RGB", (200, 100), color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes.read()


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "service" in data


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check endpoint."""
    response = client.get("/ready")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["ready"] is True


def test_upload_valid_image(client: TestClient, sample_image_bytes: bytes) -> None:
    """Test uploading a valid image file."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}

    with patch("services.api.main.ocr_service.extract_text") as mock_ocr:
        mock_ocr.return_value = OCRResult(text="Sample extracted text", success=True)

        response = client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "document_id" in data
        assert data["text"] == "Sample extracted text"
        assert "extracted_data" in data
        assert data["extracted_data"] is None  # Not requested, should be None


def test_upload_with_extract_fields_parameter(
    client: TestClient, sample_image_bytes: bytes
) -> None:
    """Test upload endpoint with LLM extraction enabled."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}

    # Mock both OCR and extraction services
    with (
        patch("services.api.main.ocr_service.extract_text") as mock_ocr,
        patch("services.api.main.extraction_service.extract_invoice_fields") as mock_extract,
    ):
        mock_ocr.return_value = OCRResult(text="Sample invoice text", success=True)

        # Mock successful extraction
        sample_invoice_data = InvoiceData(
            invoice_number="INV-12345",
            invoice_date="2024-01-15",
            total_amount=1000.00,
            currency="USD",
        )
        mock_extract.return_value = ExtractionResult(
            invoice_data=sample_invoice_data, success=True, provider="openai"
        )

        # Test with extract_fields=true
        response = client.post("/api/v1/documents/upload?extract_fields=true", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["text"] == "Sample invoice text"
        assert data["extracted_data"] is not None
        assert data["extracted_data"]["invoice_number"] == "INV-12345"
        assert data["extracted_data"]["total_amount"] == "1000.0"  # Decimal serialized
        assert data["extracted_data"]["currency"] == "USD"

        # Verify extraction service was called
        mock_extract.assert_called_once_with("Sample invoice text")


def test_upload_with_extraction_failure_graceful_degradation(
    client: TestClient, sample_image_bytes: bytes
) -> None:
    """Test that OCR succeeds even if LLM extraction fails."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}

    # Mock OCR success but extraction failure
    with (
        patch("services.api.main.ocr_service.extract_text") as mock_ocr,
        patch("services.api.main.extraction_service.extract_invoice_fields") as mock_extract,
    ):
        mock_ocr.return_value = OCRResult(text="Sample invoice text", success=True)

        # Mock extraction failure
        mock_extract.return_value = ExtractionResult(
            invoice_data=None, success=False, error="API key not set", provider="openai"
        )

        # Test with extract_fields=true
        response = client.post("/api/v1/documents/upload?extract_fields=true", files=files)

        # Request should still succeed (OCR succeeded)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["text"] == "Sample invoice text"
        # Extraction failed, so extracted_data should be None
        assert data["extracted_data"] is None


def test_extraction_metrics_recorded(client: TestClient, sample_image_bytes: bytes) -> None:
    """Test that extraction metrics are recorded properly."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}

    # Import metrics module to check counters
    from services.api import metrics

    # Get initial metric values
    initial_success = metrics.extraction_requests_total.labels(status="success")._value.get()
    initial_failed = metrics.extraction_requests_total.labels(status="failed")._value.get()

    # Mock successful extraction
    with (
        patch("services.api.main.ocr_service.extract_text") as mock_ocr,
        patch("services.api.main.extraction_service.extract_invoice_fields") as mock_extract,
    ):
        mock_ocr.return_value = OCRResult(text="Sample text", success=True)
        sample_data = InvoiceData(invoice_number="INV-001", currency="USD")
        mock_extract.return_value = ExtractionResult(
            invoice_data=sample_data, success=True, provider="openai"
        )

        # Make request with extraction enabled
        client.post("/api/v1/documents/upload?extract_fields=true", files=files)

    # Check success counter incremented
    final_success = metrics.extraction_requests_total.labels(status="success")._value.get()
    assert final_success == initial_success + 1

    # Mock failed extraction
    with (
        patch("services.api.main.ocr_service.extract_text") as mock_ocr,
        patch("services.api.main.extraction_service.extract_invoice_fields") as mock_extract,
    ):
        mock_ocr.return_value = OCRResult(text="Sample text", success=True)
        mock_extract.return_value = ExtractionResult(
            invoice_data=None, success=False, error="Failed", provider="openai"
        )

        # Make request with extraction enabled
        client.post("/api/v1/documents/upload?extract_fields=true", files=files)

    # Check failed counter incremented
    final_failed = metrics.extraction_requests_total.labels(status="failed")._value.get()
    assert final_failed == initial_failed + 1


def test_upload_no_file(client: TestClient) -> None:
    """Test upload endpoint with no file."""
    response = client.post("/api/v1/documents/upload")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_upload_invalid_file_type(client: TestClient) -> None:
    """Test upload endpoint with invalid file type."""
    files = {"file": ("test.txt", b"Not an image", "text/plain")}

    response = client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "detail" in data


def test_upload_empty_file(client: TestClient) -> None:
    """Test upload endpoint with empty file."""
    files = {"file": ("test.png", b"", "image/png")}

    response = client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "detail" in data


def test_metrics_endpoint(client: TestClient) -> None:
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")

    assert response.status_code == status.HTTP_200_OK
    # Check for Prometheus/OpenMetrics format
    content_type = response.headers["content-type"]
    assert "openmetrics-text" in content_type or "text/plain" in content_type
    # Check for some expected metrics
    content = response.text
    assert "http_requests_total" in content or "# HELP" in content


def test_metrics_recorded_on_requests(client: TestClient) -> None:
    """Test that metrics are recorded on API requests."""
    # Make a health check request
    client.get("/health")

    # Get metrics
    response = client.get("/metrics")
    content = response.text

    # Verify that http_requests_total metric exists
    assert "http_requests_total" in content
