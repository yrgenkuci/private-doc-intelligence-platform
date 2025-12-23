"""Ollama-based extraction provider for self-hosted LLM inference.

Uses local Ollama server for structured data extraction from OCR text.
Supports data sovereignty requirements by running entirely on-premises.

Requires Ollama server running on localhost:11434.
See: https://ollama.ai/
"""

import json
import logging
import re
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from services.extraction.base import ExtractionProvider, ExtractionResult
from services.extraction.schema import InvoiceData
from services.shared.config import Settings

logger = logging.getLogger(__name__)


class OllamaExtractionProvider(ExtractionProvider):
    """Ollama-based extraction provider for self-hosted LLM inference.

    Uses local Ollama server running on localhost:11434.
    Supports models like Qwen2.5, Llama3, Mistral.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Ollama extraction provider.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._client = httpx.Client(timeout=120.0)  # LLMs can be slow

    @property
    def provider_name(self) -> str:
        """Get provider name for logging/metrics.

        Returns:
            Provider identifier 'ollama'
        """
        return "ollama"

    def is_available(self) -> bool:
        """Check if Ollama server is running and model is available.

        Returns:
            True if Ollama server responds and model is loaded
        """
        try:
            response = self._client.get(f"{self._base_url}/api/tags")
            if response.status_code != 200:
                return False
            # Check if configured model is available
            models = response.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]
            return self._model.split(":")[0] in model_names
        except Exception:
            return False

    def extract_invoice_fields(self, ocr_text: str) -> ExtractionResult:
        """Extract structured invoice data from OCR text using Ollama.

        Args:
            ocr_text: Raw text from OCR engine

        Returns:
            ExtractionResult with structured invoice data or error
        """
        if not ocr_text or not ocr_text.strip():
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error="Empty OCR text provided",
                provider=self.provider_name,
            )

        try:
            # Build prompt
            prompt = self._build_extraction_prompt(ocr_text)

            # Call Ollama with retry logic
            response_text = self._call_ollama_with_retry(prompt)

            # Parse JSON from response
            invoice_dict = self._parse_json_response(response_text)

            # Convert to Pydantic model
            invoice_data = InvoiceData(**invoice_dict)

            return ExtractionResult(
                invoice_data=invoice_data,
                success=True,
                provider=self.provider_name,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from Ollama response: {e}")
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error=f"JSON parsing failed: {str(e)}",
                provider=self.provider_name,
            )
        except Exception as e:
            logger.error(f"Ollama extraction failed: {e}")
            return ExtractionResult(
                invoice_data=None,
                success=False,
                error=f"Extraction failed: {str(e)}",
                provider=self.provider_name,
            )

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_ollama_with_retry(self, prompt: str) -> str:
        """Call Ollama API with retry logic for transient errors.

        Args:
            prompt: Extraction prompt for the LLM

        Returns:
            Raw response text from Ollama

        Raises:
            httpx.HTTPError: After all retry attempts exhausted
        """
        response = self._client.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,  # Deterministic output
                    "num_predict": 1024,  # Max tokens
                },
            },
        )
        response.raise_for_status()
        result: str = response.json().get("response", "")
        return result

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM response.

        Handles common LLM quirks like markdown code blocks.

        Args:
            response_text: Raw LLM response

        Returns:
            Parsed JSON dict

        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
        if json_match:
            result: dict[str, Any] = json.loads(json_match.group(1).strip())
            return result

        # Try to find JSON object directly
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            result = json.loads(json_match.group(0))
            return result

        # Try parsing entire response
        result = json.loads(response_text.strip())
        return result

    def _build_extraction_prompt(self, ocr_text: str) -> str:
        """Build prompt for LLM extraction with few-shot examples.

        Args:
            ocr_text: Raw OCR text

        Returns:
            Formatted prompt string
        """
        # Schema definition for JSON output
        schema = (
            '{"invoice_number": string|null, "invoice_date": string|null (YYYY-MM-DD), '
            '"due_date": string|null, "supplier_name": string|null, '
            '"supplier_address": string|null, "customer_name": string|null, '
            '"subtotal": number|null, "tax_amount": number|null, '
            '"total_amount": number|null, "currency": string|null}'
        )

        # Example 1: Seller/Client format
        example1_input = (
            "Invoice no: 84652373 Date of issue: 02/23/2021 Seller: Client: "
            "Nguyen-Roach Clark-Foster 247 David Highway Lake John, WV 84178 "
            "SUMMARY Net worth VAT Gross worth 211,77 21,18 232,95 Total $ 232,95"
        )
        example1_output = (
            '{"invoice_number": "84652373", "invoice_date": "2021-02-23", '
            '"due_date": null, "supplier_name": "Nguyen-Roach", '
            '"supplier_address": "247 David Highway, Lake John, WV 84178", '
            '"customer_name": "Clark-Foster", "subtotal": 211.77, '
            '"tax_amount": 21.18, "total_amount": 232.95, "currency": "USD"}'
        )

        # Example 2: Standard format
        example2_input = (
            "INVOICE #INV-12345 Date: January 15, 2024 Bill To: ABC Corp "
            "From: XYZ Suppliers Subtotal: $1,000.00 Tax: $100.00 Total: $1,100.00"
        )
        example2_output = (
            '{"invoice_number": "INV-12345", "invoice_date": "2024-01-15", '
            '"due_date": null, "supplier_name": "XYZ Suppliers", '
            '"supplier_address": null, "customer_name": "ABC Corp", '
            '"subtotal": 1000.00, "tax_amount": 100.00, '
            '"total_amount": 1100.00, "currency": "USD"}'
        )

        return f"""You are an invoice data extraction assistant. \
Extract invoice information from OCR text and return ONLY valid JSON.

SCHEMA (use null for missing fields):
{schema}

EXAMPLES:

Input: "{example1_input}"
Output: {example1_output}

Input: "{example2_input}"
Output: {example2_output}

INSTRUCTIONS:
- "Seller:" = supplier, "Client:" or "Bill To:" = customer
- Convert dates: MM/DD/YYYY -> YYYY-MM-DD
- Convert European decimals: 211,77 -> 211.77
- "Net worth" = subtotal, "Gross worth"/"Total" = total_amount
- Format address: "street, city, state zip"
- Return ONLY JSON, no explanation

INPUT:
{ocr_text}

OUTPUT:"""
