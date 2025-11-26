"""Local model-based extraction provider (stub implementation).

This is a STUB implementation that returns empty invoice data.
Full implementation with Donut/LayoutLM will be added in Phase 2b.

Planned local model options for production:
- Donut: https://huggingface.co/naver-clova-ix/donut-base-docvqa
  * End-to-end document understanding without OCR dependency
  * ~250M parameters, 4-6GB VRAM for inference
  * Inference: ~1-2 seconds per document on GPU

- LayoutLMv3: https://huggingface.co/microsoft/layoutlmv3-base
  * Document understanding with text + layout + image
  * ~130M parameters, 6-8GB VRAM recommended
  * Requires preprocessing (OCR + layout detection)

Production requirements (Phase 2b):
- Dependencies: transformers>=4.25.0, torch>=2.0.0, pillow>=10.0.0
- Hardware: GPU with 4-8GB VRAM (NVIDIA T4 or better)
- Model files: Downloaded and cached locally (~1-2GB)
- Inference optimization: ONNX or TorchScript for speed

Current stub behavior:
- Returns empty InvoiceData (all fields None)
- Always reports as available
- No external dependencies
- Enables testing of provider switching infrastructure
"""

import logging

from services.extraction.base import ExtractionProvider, ExtractionResult
from services.extraction.schema import InvoiceData
from services.shared.config import Settings

logger = logging.getLogger(__name__)


class LocalExtractionProvider(ExtractionProvider):
    """Local model-based extraction provider (stub implementation).

    This is a stub that will be replaced with actual model implementation
    in Phase 2b. Currently returns empty invoice data to enable testing
    of the provider switching infrastructure.

    Future implementation will use:
    - Donut or LayoutLMv3 for document understanding
    - Local model files (no cloud API calls)
    - GPU acceleration for inference
    - Caching for repeated extractions
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize local extraction provider.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        logger.warning(
            "LocalExtractionProvider is a STUB implementation. "
            "Returns empty invoice data. "
            "Full model integration planned for Phase 2b."
        )

    @property
    def provider_name(self) -> str:
        """Get provider name for logging/metrics.

        Returns:
            Provider identifier 'local'
        """
        return "local"

    def is_available(self) -> bool:
        """Check if local model is available.

        Currently always returns True (stub mode).

        In production (Phase 2b), this will check for:
        - Model files present in cache directory
        - Required dependencies installed (transformers, torch)
        - Sufficient GPU memory available
        - Model loaded successfully

        Returns:
            True (stub always available)
        """
        return True

    def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
        """Extract invoice fields using local model (stub).

        This stub implementation returns empty InvoiceData to enable
        testing of provider switching without requiring actual model files.

        Phase 2b implementation will:
        1. Preprocess OCR text and/or image
        2. Run inference with local model (Donut/LayoutLM)
        3. Post-process model output to InvoiceData schema
        4. Return structured results with confidence scores

        Args:
            ocr_text: Raw text from OCR engine

        Returns:
            ExtractionResult with empty invoice data (stub)
        """
        if not ocr_text or not ocr_text.strip():
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error="Empty OCR text provided",
                provider=self.provider_name,
            )

        # Stub implementation: return empty invoice data
        logger.info("Using STUB local extraction (returns empty InvoiceData)")
        logger.debug(f"OCR text length: {len(ocr_text)} characters")

        # Create empty invoice data with all fields explicitly set to None
        # In Phase 2b, this will contain actual extracted values from local model
        return ExtractionResult(
            invoice_data=InvoiceData(
                invoice_number=None,
                invoice_date=None,
                due_date=None,
                supplier_name=None,
                supplier_address=None,
                customer_name=None,
                subtotal=None,
                tax_amount=None,
                total_amount=None,
                currency="USD",  # Default value
                confidence_score=None,
            ),
            success=True,
            error=None,
            provider=self.provider_name,
        )
