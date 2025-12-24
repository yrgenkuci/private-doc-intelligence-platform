"""OCR service using Tesseract.

Production-grade OCR implementation with:
- Configurable Tesseract path via environment variables
- Comprehensive error handling
- Type-safe results using Pydantic

Based on pytesseract documentation:
https://github.com/madmaze/pytesseract
"""

import os
from pathlib import Path

import pytesseract
from PIL import Image
from pydantic import BaseModel

from services.shared.config import Settings


class OCRResult(BaseModel):
    """Result of OCR operation.

    Attributes:
        text: Extracted text content
        success: Whether operation succeeded
        error: Error message if operation failed
    """

    text: str
    success: bool
    error: str | None = None


class OCRService:
    """OCR service using Tesseract engine.

    Handles text extraction from images with proper error handling
    and configuration management.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize OCR service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._configure_tesseract()

    def _configure_tesseract(self) -> None:
        """Configure Tesseract command path from environment.

        Allows overriding default Tesseract path via TESSERACT_CMD environment variable.
        Common paths:
        - Linux: /usr/bin/tesseract
        - macOS: /opt/homebrew/bin/tesseract or /usr/local/bin/tesseract
        - Windows: C:\\Program Files\\Tesseract-OCR\\tesseract.exe
        """
        tesseract_cmd = os.getenv("TESSERACT_CMD")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def extract_text(self, image_path: Path) -> OCRResult:
        """Extract text from image file.

        Args:
            image_path: Path to image file

        Returns:
            OCRResult with extracted text or error information
        """
        try:
            if not image_path.exists():
                return OCRResult(
                    text="", success=False, error=f"Image file not found: {image_path}"
                )

            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)

            return OCRResult(text=text, success=True)

        except Exception as e:
            return OCRResult(text="", success=False, error=f"OCR processing failed: {str(e)}")
