"""Unit tests for OCR service.

Tests cover:
- Text extraction from valid images
- Error handling for invalid files
- Configuration management
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from services.ocr.service import OCRResult, OCRService
from services.shared.config import Settings


@pytest.fixture
def test_image_path(tmp_path: Path) -> Path:
    """Create a simple test image with text."""
    img_path = tmp_path / "test_image.png"
    # Create a simple white image
    img = Image.new("RGB", (200, 50), color="white")
    img.save(img_path)
    return img_path


@pytest.fixture
def ocr_service() -> OCRService:
    """Create OCR service instance."""
    settings = Settings()
    return OCRService(settings)


def test_ocr_service_initialization(ocr_service: OCRService) -> None:
    """Test that OCR service initializes correctly."""
    assert ocr_service is not None
    assert isinstance(ocr_service.settings, Settings)


@patch("services.ocr.service.pytesseract.image_to_string")
def test_extract_text_success(
    mock_ocr: MagicMock, ocr_service: OCRService, test_image_path: Path
) -> None:
    """Test successful text extraction from image."""
    mock_ocr.return_value = "Sample extracted text"

    result = ocr_service.extract_text(test_image_path)

    assert isinstance(result, OCRResult)
    assert result.text == "Sample extracted text"
    assert result.success is True
    assert result.error is None
    mock_ocr.assert_called_once()


def test_extract_text_file_not_found(ocr_service: OCRService) -> None:
    """Test error handling for non-existent file."""
    non_existent = Path("/non/existent/file.png")

    result = ocr_service.extract_text(non_existent)

    assert result.success is False
    assert result.text == ""
    assert result.error is not None
    assert "not found" in result.error.lower()


def test_extract_text_invalid_image(ocr_service: OCRService, tmp_path: Path) -> None:
    """Test error handling for invalid image file."""
    invalid_file = tmp_path / "not_an_image.txt"
    invalid_file.write_text("This is not an image")

    result = ocr_service.extract_text(invalid_file)

    assert result.success is False
    assert result.text == ""
    assert result.error is not None


@patch("services.ocr.service.pytesseract.image_to_string")
def test_extract_text_empty_result(
    mock_ocr: MagicMock, ocr_service: OCRService, test_image_path: Path
) -> None:
    """Test handling of empty OCR result."""
    mock_ocr.return_value = ""

    result = ocr_service.extract_text(test_image_path)

    assert result.success is True
    assert result.text == ""
    assert result.error is None
