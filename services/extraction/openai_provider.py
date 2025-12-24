"""OpenAI-based extraction provider for invoice field extraction.

Uses OpenAI API for structured data extraction from OCR text.
Based on OpenAI function calling / structured outputs pattern.

Includes retry logic with exponential backoff for transient API errors.

This provider uses cloud-based OpenAI API. For self-hosted/local inference,
use LocalExtractionProvider instead.
"""

import json
import os
from typing import Any

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from services.extraction.base import ExtractionProvider, ExtractionResult
from services.extraction.schema import InvoiceData
from services.shared.config import Settings


class OpenAIExtractionProvider(ExtractionProvider):
    """OpenAI-based extraction provider using GPT-4o-mini.

    Uses OpenAI API with function calling for structured outputs.
    Requires OPENAI_API_KEY environment variable.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize OpenAI extraction provider.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        self._client: OpenAI | None = None

    @property
    def provider_name(self) -> str:
        """Get provider name for logging/metrics.

        Returns:
            Provider identifier 'openai'
        """
        return "openai"

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured.

        Returns:
            True if OPENAI_API_KEY environment variable is set
        """
        return os.getenv("OPENAI_API_KEY") is not None

    def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
        """Extract structured invoice data from OCR text using OpenAI.

        Args:
            ocr_text: Raw text from OCR engine

        Returns:
            ExtractionResult with structured invoice data or error, provider='openai'
        """
        # Check for API key at runtime
        if not self.is_available():
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error="OPENAI_API_KEY environment variable not set",
                provider=self.provider_name,
            )

        if not ocr_text or not ocr_text.strip():
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error="Empty OCR text provided",
                provider=self.provider_name,
            )

        try:
            # Initialize client if not already done
            api_key = os.getenv("OPENAI_API_KEY")
            if self._client is None or self._client.api_key != api_key:
                self._client = OpenAI(api_key=api_key)

            # Create extraction prompt
            prompt = self._build_extraction_prompt(ocr_text)

            # Call OpenAI with retry logic
            response = self._call_openai_with_retry(prompt)

            # Parse response
            message = response.choices[0].message
            if message.function_call is None:
                return ExtractionResult(
                    invoice_data=None,
                    success=False,
                    error="No function call in API response",
                    provider=self.provider_name,
                )

            invoice_dict = json.loads(message.function_call.arguments)

            # Convert to Pydantic model
            invoice_data = InvoiceData(**invoice_dict)

            return ExtractionResult(
                invoice_data=invoice_data,
                success=True,
                provider=self.provider_name,
            )

        except Exception as e:
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error=f"Extraction failed: {str(e)}",
                provider=self.provider_name,
            )

    @retry(
        retry=retry_if_exception_type((Exception,)),  # Retry on transient errors
        wait=wait_exponential_jitter(initial=1, max=60),  # Exponential backoff with jitter
        stop=stop_after_attempt(3),  # Max 3 attempts
        reraise=True,  # Re-raise exception after max attempts
    )
    def _call_openai_with_retry(self, prompt: str) -> Any:
        """Call OpenAI API with retry logic for transient errors.

        Uses exponential backoff with jitter to handle rate limits and temporary failures.
        Retries up to 3 times with increasing delays (1s, 2-4s, 4-8s, up to 60s max).

        Args:
            prompt: Extraction prompt for the LLM

        Returns:
            OpenAI API response

        Raises:
            Exception: After all retry attempts are exhausted
        """
        if self._client is None:
            raise RuntimeError("OpenAI client not initialized")

        # Call OpenAI with function calling for structured output
        # NOTE: Using function_call (legacy) instead of tools API because:
        # 1. function_call still fully supported by OpenAI (no deprecation deadline)
        # 2. Our use case is simple: single extraction function
        # 3. tools API is more complex, offers no benefit for our current needs
        # 4. Migrate to tools when: (a) need multiple tools, (b) need built-in tools,
        #    or (c) OpenAI announces deprecation timeline
        return self._client.chat.completions.create(  # type: ignore[call-overload]
            model="gpt-4o-mini",  # Cost-effective model with good accuracy
            messages=[
                {
                    "role": "system",
                    "content": "You are an invoice data extraction assistant.",
                },
                {"role": "user", "content": prompt},
            ],
            functions=[self._get_invoice_schema()],
            function_call={"name": "extract_invoice_data"},
            temperature=0,  # Deterministic output
        )

    def _build_extraction_prompt(self, ocr_text: str) -> str:
        """Build prompt for LLM extraction with few-shot examples.

        Uses few-shot learning to improve extraction accuracy by providing
        examples of invoice OCR text and expected structured output.

        Args:
            ocr_text: Raw OCR text

        Returns:
            Formatted prompt string with examples
        """
        return f"""Extract invoice information from OCR text and return structured data.

Example 1 (Standard format):
OCR Text: "INVOICE #INV-12345\\nDate: January 15, 2024\\nDue: February 15, 2024\\n\
Bill To: ABC Corp\\nFrom: XYZ Suppliers Inc\\n123 Main Street\\n\
Subtotal: $1,000.00\\nTax (10%): $100.00\\nTotal: $1,100.00"

Expected Output: {{"invoice_number": "INV-12345", "invoice_date": "2024-01-15", \
"due_date": "2024-02-15", "customer_name": "ABC Corp", \
"supplier_name": "XYZ Suppliers Inc", "supplier_address": "123 Main Street", \
"subtotal": 1000.00, "tax_amount": 100.00, "total_amount": 1100.00, "currency": "USD"}}

Example 2 (Seller/Client side-by-side format):
OCR Text: "Invoice no: 84652373 Date of issue: 02/23/2021 Seller: Client: \
Nguyen-Roach Clark-Foster 247 David Highway 77477 Cliff Apt. 853 \
Lake John, WV 84178 Washingtonbury, MS 78346 Tax Id: 991-72-5826 \
SUMMARY VAT [%] Net worth VAT Gross worth 10% 211,77 21,18 232,95 Total $ 232,95"

Expected Output: {{"invoice_number": "84652373", "invoice_date": "2021-02-23", \
"supplier_name": "Nguyen-Roach", "supplier_address": "247 David Highway, Lake John, WV 84178", \
"customer_name": "Clark-Foster", \
"subtotal": 211.77, "tax_amount": 21.18, "total_amount": 232.95, "currency": "USD"}}

Example 3 (European format):
OCR Text: "Invoice Number: 2024-001\\nIssued: 03/10/2024\\n\
Client: Tech Solutions Ltd\\nVendor: Office Supplies Co\\n\
Amount Due: EUR 850.00\\nVAT (20%): EUR 170.00\\nGrand Total: EUR 1,020.00"

Expected Output: {{"invoice_number": "2024-001", "invoice_date": "2024-03-10", \
"customer_name": "Tech Solutions Ltd", "supplier_name": "Office Supplies Co", \
"subtotal": 850.00, "tax_amount": 170.00, "total_amount": 1020.00, "currency": "EUR"}}

CRITICAL Instructions for parsing:
- When you see "Seller: Client:" the FIRST company name is the seller, SECOND is the client
- For addresses in side-by-side format: Look for Tax Id patterns to find address boundaries
- The seller address is between seller name and "Tax Id: XXX-XX-XXXX" (first Tax Id)
- "Net worth" in SUMMARY = subtotal (before tax)
- "Gross worth" or "Total" = total_amount (after tax)
- Parse dates: "02/23/2021" -> "2021-02-23" (MM/DD/YYYY to YYYY-MM-DD)
- European decimals: "211,77" -> 211.77 (comma is decimal separator)
- Return null for any field not clearly present

ADDRESS EXTRACTION (critical):
- Include FULL street with Suite/Apt numbers: "33771 Powell Pike Suite 054"
- Include city PREFIXES (East, West, North, South, Lake, New): "East Zacharyville" not "Zacharyville"
- Format: "street, city, state zip" with comma between street and city
- Example: "45558 Davis Mountains, East Zacharyville, IA 99376"
- When OCR shows interleaved addresses like:
  "247 David Highway 77477 Cliff Apt. 853 Lake John, WV 84178 Washingtonbury, MS 78346"
  The SELLER address ends at first "Tax Id:" - extract: "247 David Highway, Lake John, WV 84178"

OCR Text:
{ocr_text}

Extract the invoice data. For supplier_address, extract ONLY the seller's full address with all parts."""

    def _get_invoice_schema(self) -> dict[str, Any]:
        """Get OpenAI function calling schema for InvoiceData.

        Returns:
            Function definition dict for OpenAI API
        """
        return {
            "name": "extract_invoice_data",
            "description": "Extract structured invoice data from OCR text",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_number": {"type": ["string", "null"]},
                    "invoice_date": {"type": ["string", "null"], "format": "date"},
                    "due_date": {"type": ["string", "null"], "format": "date"},
                    "supplier_name": {"type": ["string", "null"]},
                    "supplier_address": {"type": ["string", "null"]},
                    "customer_name": {"type": ["string", "null"]},
                    "subtotal": {"type": ["number", "null"]},
                    "tax_amount": {"type": ["number", "null"]},
                    "total_amount": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"]},
                    "confidence_score": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                },
            },
        }
