"""Unit tests for PaddleOCR service and OCR factory."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.ocr.factory import create_ocr_service
from services.ocr.paddle_service import PaddleOCRService
from services.shared.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(ocr_provider="paddleocr")


@pytest.fixture
def tesseract_settings() -> Settings:
    """Create test settings for Tesseract."""
    return Settings(ocr_provider="tesseract")


class TestPaddleOCRService:
    """Test PaddleOCRService class."""

    def test_is_available_when_installed(self, settings: Settings) -> None:
        """Should return True when PaddleOCR is installed."""
        service = PaddleOCRService(settings)
        # PaddleOCR is installed in this test environment
        assert service.is_available() is True

    def test_extract_text_file_not_found(self, settings: Settings) -> None:
        """Should return error for non-existent file."""
        service = PaddleOCRService(settings)
        result = service.extract_text(Path("/nonexistent/image.jpg"))
        assert result.success is False
        assert "not found" in str(result.error).lower()

    def test_extract_text_success_with_mock(self, settings: Settings) -> None:
        """Should extract text successfully with mocked PaddleOCR."""
        service = PaddleOCRService(settings)

        # Mock the OCR result
        mock_ocr_result = MagicMock()
        mock_ocr_result.get.side_effect = lambda key, default=None: {
            "rec_texts": ["Invoice #12345", "Total: $100.00"],
            "rec_scores": [0.95, 0.98],
        }.get(key, default)

        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [mock_ocr_result]

        with patch.object(service, "_get_ocr", return_value=mock_ocr):
            # Create a temp file for testing
            with patch("pathlib.Path.exists", return_value=True):
                result = service.extract_text(Path("test.jpg"))

        assert result.success is True
        assert "Invoice #12345" in result.text
        assert result.confidence == pytest.approx(0.965, rel=0.01)

    def test_extract_text_empty_result(self, settings: Settings) -> None:
        """Should handle empty OCR result gracefully."""
        service = PaddleOCRService(settings)

        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [None]

        with patch.object(service, "_get_ocr", return_value=mock_ocr):
            with patch("pathlib.Path.exists", return_value=True):
                result = service.extract_text(Path("empty.jpg"))

        assert result.success is True
        assert result.text == ""

    def test_lazy_loading(self, settings: Settings) -> None:
        """Should not load model until first extraction."""
        service = PaddleOCRService(settings)
        # Model should not be loaded yet
        assert service._ocr is None

    def test_environment_configured(self, settings: Settings) -> None:
        """Should set DISABLE_MODEL_SOURCE_CHECK environment variable."""
        import os

        PaddleOCRService(settings)
        assert os.environ.get("DISABLE_MODEL_SOURCE_CHECK") == "True"


class TestOCRFactory:
    """Test OCR factory function."""

    def test_create_tesseract_service(self, tesseract_settings: Settings) -> None:
        """Should create Tesseract service when configured."""
        service = create_ocr_service(tesseract_settings)
        # Check it's the Tesseract service by class name
        assert "OCRService" in type(service).__name__

    def test_create_paddleocr_service(self, settings: Settings) -> None:
        """Should create PaddleOCR service when configured."""
        service = create_ocr_service(settings)
        assert isinstance(service, PaddleOCRService)

    def test_invalid_provider_raises_error(self) -> None:
        """Should raise ValueError for unknown provider."""
        settings = Settings()
        # Directly modify the attribute for testing
        object.__setattr__(settings, "ocr_provider", "invalid")

        with pytest.raises(ValueError, match="Unknown OCR provider"):
            create_ocr_service(settings)


class TestOCRProviderConfig:
    """Test OCR provider configuration."""

    def test_default_provider_is_tesseract(self) -> None:
        """Default OCR provider should be Tesseract."""
        settings = Settings()
        assert settings.ocr_provider == "tesseract"

    def test_paddleocr_provider_via_env(self) -> None:
        """Should support PaddleOCR provider via environment."""
        import os

        os.environ["APP_OCR_PROVIDER"] = "paddleocr"
        try:
            settings = Settings()
            assert settings.ocr_provider == "paddleocr"
        finally:
            del os.environ["APP_OCR_PROVIDER"]
