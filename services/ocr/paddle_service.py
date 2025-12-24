"""PaddleOCR service for GPU-accelerated text extraction.

Production-grade OCR implementation with:
- GPU acceleration support (optional)
- Multilingual text recognition
- Layout analysis capability
- Lazy model loading for faster startup

Based on PaddleOCR v3.x:
https://github.com/PaddlePaddle/PaddleOCR
"""

import logging
import os
from pathlib import Path

from pydantic import BaseModel

from services.shared.config import Settings

logger = logging.getLogger(__name__)


class OCRResult(BaseModel):
    """Result of OCR operation.

    Attributes:
        text: Extracted text content
        success: Whether operation succeeded
        error: Error message if operation failed
        confidence: Average confidence score (0-1)
    """

    text: str
    success: bool
    error: str | None = None
    confidence: float | None = None


class PaddleOCRService:
    """OCR service using PaddleOCR engine.

    Handles text extraction from images with GPU acceleration support
    and lazy model loading.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize PaddleOCR service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._ocr: object | None = None  # Lazy loading (PaddleOCR instance)
        self._configure_environment()

    def _configure_environment(self) -> None:
        """Configure environment for PaddleOCR.

        Disables model source check for faster startup.
        """
        os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")

    def _get_ocr(self) -> object:
        """Get or initialize PaddleOCR instance (lazy loading).

        Returns:
            Initialized PaddleOCR instance
        """
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                logger.info("Initializing PaddleOCR engine...")
                self._ocr = PaddleOCR(lang="en")
                logger.info("PaddleOCR initialized successfully")
            except ImportError as e:
                raise ImportError(
                    "PaddleOCR not installed. Install with: " "pip install paddlepaddle paddleocr"
                ) from e
        return self._ocr

    def is_available(self) -> bool:
        """Check if PaddleOCR is available.

        Returns:
            True if PaddleOCR can be imported
        """
        try:
            from paddleocr import PaddleOCR  # noqa: F401

            return True
        except ImportError:
            return False

    def extract_text(self, image_path: Path) -> OCRResult:
        """Extract text from image file using PaddleOCR.

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

            # Get OCR instance (lazy load)
            ocr = self._get_ocr()

            # Run OCR (dynamic call on lazy-loaded PaddleOCR instance)
            result = ocr.ocr(str(image_path))  # type: ignore[attr-defined]

            if not result or not result[0]:
                return OCRResult(
                    text="",
                    success=True,
                    confidence=0.0,
                )

            # Extract text and confidence from v3.x result format
            ocr_result = result[0]

            # Get recognized texts
            texts = ocr_result.get("rec_texts", [])
            scores = ocr_result.get("rec_scores", [])

            # Join texts with newlines (preserving document structure)
            full_text = "\n".join(texts)

            # Calculate average confidence
            avg_confidence = sum(scores) / len(scores) if scores else 0.0

            return OCRResult(
                text=full_text,
                success=True,
                confidence=avg_confidence,
            )

        except Exception as e:
            logger.error(f"PaddleOCR processing failed: {e}")
            return OCRResult(text="", success=False, error=f"OCR processing failed: {str(e)}")
