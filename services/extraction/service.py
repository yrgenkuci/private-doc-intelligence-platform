"""Extraction service factory and backward compatibility.

This module maintains backward compatibility with existing code while
enabling the new model switching infrastructure.

For new code, prefer importing specific providers:
- OpenAIExtractionProvider for OpenAI-based extraction
- LocalExtractionProvider for self-hosted model extraction
- create_extraction_service() factory for configuration-based selection

Legacy import (backward compatible):
    from services.extraction.service import ExtractionService
"""

from services.extraction.base import ExtractionProvider, ExtractionResult
from services.extraction.openai_provider import OpenAIExtractionProvider
from services.extraction.schema import InvoiceData

# Backward compatibility: ExtractionService is an alias to OpenAI provider
# This ensures existing code continues to work without modifications
ExtractionService = OpenAIExtractionProvider


__all__ = [
    "ExtractionService",  # Backward compatibility alias
    "ExtractionProvider",  # Base interface
    "ExtractionResult",  # Result model
    "InvoiceData",  # Schema
    "OpenAIExtractionProvider",  # Concrete provider
]
