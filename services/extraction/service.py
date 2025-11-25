"""LLM extraction service for invoice field extraction.

Uses OpenAI API for structured data extraction from OCR text.
Based on OpenAI function calling / structured outputs pattern.

Includes retry logic with exponential backoff for transient API errors.

Alternative: Can be replaced with local models (LayoutLM, Donut) in future.
"""

import json
import os
from typing import Any

from openai import OpenAI
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from services.extraction.schema import InvoiceData
from services.shared.config import Settings


class ExtractionResult(BaseModel):
    """Result of extraction operation."""

    invoice_data: InvoiceData | None
    success: bool
    error: str | None = None


class ExtractionService:
    """Service for extracting structured data from OCR text using LLM.

    Uses OpenAI API with structured outputs for reliable field extraction.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize extraction service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._client: OpenAI | None = None

    def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
        """Extract structured invoice data from OCR text.

        Args:
            ocr_text: Raw text from OCR engine

        Returns:
            ExtractionResult with structured invoice data or error
        """
        # Check for API key at runtime
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error="OPENAI_API_KEY environment variable not set",
            )

        if not ocr_text or not ocr_text.strip():
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error="Empty OCR text provided",
            )

        try:
            # Initialize client if not already done
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
                )

            invoice_dict = json.loads(message.function_call.arguments)

            # Convert to Pydantic model
            invoice_data = InvoiceData(**invoice_dict)

            return ExtractionResult(invoice_data=invoice_data, success=True)

        except Exception as e:
            return ExtractionResult(
                invoice_data=None, success=False, error=f"Extraction failed: {str(e)}"
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

Example 1:
OCR Text: "INVOICE #INV-12345\\nDate: January 15, 2024\\nDue: February 15, 2024\\n\
Bill To: ABC Corp\\nFrom: XYZ Suppliers Inc\\n123 Main Street\\n\
Subtotal: $1,000.00\\nTax (10%): $100.00\\nTotal: $1,100.00"

Expected Output: {{"invoice_number": "INV-12345", "invoice_date": "2024-01-15", \
"due_date": "2024-02-15", "customer_name": "ABC Corp", \
"supplier_name": "XYZ Suppliers Inc", "supplier_address": "123 Main Street", \
"subtotal": 1000.00, "tax_amount": 100.00, "total_amount": 1100.00, "currency": "USD"}}

Example 2:
OCR Text: "Invoice Number: 2024-001\\nIssued: 03/10/2024\\n\
Client: Tech Solutions Ltd\\nVendor: Office Supplies Co\\n\
Amount Due: €850.00\\nVAT (20%): €170.00\\nGrand Total: €1,020.00"

Expected Output: {{"invoice_number": "2024-001", "invoice_date": "2024-03-10", \
"customer_name": "Tech Solutions Ltd", "supplier_name": "Office Supplies Co", \
"subtotal": 850.00, "tax_amount": 170.00, "total_amount": 1020.00, "currency": "EUR"}}

Instructions:
- Extract all available fields from the OCR text below
- Return null for any field not found in the text
- Parse dates into YYYY-MM-DD format
- Extract numeric values without currency symbols
- Identify the currency code (USD, EUR, GBP, etc.)

OCR Text:
{ocr_text}

Extract the invoice data following the format shown in the examples."""

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
