"""Unit tests for document ingestion API.

Tests cover:
- Health check endpoints
- File upload validation
- OCR integration
"""

import io
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from PIL import Image

from services.api.main import app
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
