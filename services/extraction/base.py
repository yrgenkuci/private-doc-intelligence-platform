"""Abstract base class for extraction services.

Enables switching between different extraction providers (OpenAI, local models)
while maintaining consistent interface and type safety.

Based on Strategy Pattern:
https://refactoring.guru/design-patterns/strategy/python

Design follows existing patterns:
- Pydantic BaseModel for type-safe results (consistent with schema.py)
- ABC for interface enforcement (Python standard library)
- Settings injection (consistent with existing service initialization)
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from services.extraction.schema import InvoiceData
from services.shared.config import Settings


class ExtractionResult(BaseModel):
    """Result of extraction operation.

    Attributes:
        invoice_data: Extracted invoice data or None if extraction failed
        success: Whether operation succeeded
        error: Error message if operation failed
        provider: Name of provider that performed extraction (e.g., 'openai', 'local')
    """

    invoice_data: InvoiceData | None
    success: bool
    error: str | None = None
    provider: str  # Track which provider was used


class ExtractionProvider(ABC):
    """Abstract base class for invoice extraction providers.

    All extraction services must implement this interface to ensure
    consistent behavior and type safety. Enables Strategy Pattern for
    switching between different extraction implementations.

    Example implementations:
    - OpenAIExtractionProvider: Uses OpenAI API (cloud-based)
    - LocalExtractionProvider: Uses local models (self-hosted)
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize provider with settings.

        Args:
            settings: Application settings
        """
        self.settings = settings

    @abstractmethod
    def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
        """Extract structured invoice data from OCR text.

        Args:
            ocr_text: Raw text from OCR engine

        Returns:
            ExtractionResult with structured invoice data or error
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available/configured.

        Allows runtime checking of provider prerequisites (e.g., API keys,
        model files, dependencies).

        Returns:
            True if provider can be used, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name for logging/metrics.

        Returns:
            Provider identifier (e.g., 'openai', 'local')
        """
        pass
