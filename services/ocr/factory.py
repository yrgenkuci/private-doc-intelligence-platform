"""Factory for creating OCR services based on configuration.

Implements Factory Pattern for OCR provider selection.
Allows switching between Tesseract and PaddleOCR at runtime.
"""

import logging
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from services.shared.config import Settings

logger = logging.getLogger(__name__)


class OCRResult(BaseModel):
    """Result of OCR operation.

    Attributes:
        text: Extracted text content
        success: Whether operation succeeded
        error: Error message if operation failed
        confidence: Average confidence score (0-1), if available
    """

    text: str
    success: bool
    error: str | None = None
    confidence: float | None = None


class OCRService(Protocol):
    """Protocol for OCR services."""

    def extract_text(self, image_path: Path) -> OCRResult:
        """Extract text from image file."""
        ...

    def is_available(self) -> bool:
        """Check if OCR service is available."""
        ...


def create_ocr_service(settings: Settings) -> OCRService:
    """Factory function to create OCR service based on configuration.

    Args:
        settings: Application settings with ocr_provider field

    Returns:
        Configured OCR service instance

    Raises:
        ValueError: If configured provider is unknown
    """
    provider = settings.ocr_provider

    if provider == "tesseract":
        from services.ocr.service import OCRService as TesseractService

        logger.info("Created OCR service: tesseract")
        return TesseractService(settings)  # type: ignore[return-value]

    elif provider == "paddleocr":
        from services.ocr.paddle_service import PaddleOCRService

        service = PaddleOCRService(settings)
        if not service.is_available():
            logger.warning(
                "PaddleOCR not available. Install with: pip install paddlepaddle paddleocr"
            )
        logger.info("Created OCR service: paddleocr")
        return service  # type: ignore[return-value]

    else:
        available = ["tesseract", "paddleocr"]
        raise ValueError(f"Unknown OCR provider: '{provider}'. Available: {', '.join(available)}")
