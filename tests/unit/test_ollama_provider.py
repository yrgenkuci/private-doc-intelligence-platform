"""Unit tests for OllamaExtractionProvider.

Tests the Ollama-based extraction provider with mocked HTTP calls.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from services.extraction.ollama_provider import OllamaExtractionProvider
from services.shared.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Create test settings with Ollama provider."""
    return Settings(
        extraction_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
    )


@pytest.fixture
def provider(settings: Settings) -> OllamaExtractionProvider:
    """Create Ollama provider instance."""
    return OllamaExtractionProvider(settings)


class TestOllamaExtractionProviderProperties:
    """Test provider properties and availability."""

    def test_provider_name(self, provider: OllamaExtractionProvider) -> None:
        """Provider name should be 'ollama'."""
        assert provider.provider_name == "ollama"

    def test_is_available_when_server_running(self, provider: OllamaExtractionProvider) -> None:
        """Should return True when Ollama server responds with model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}

        with patch.object(provider._client, "get", return_value=mock_response):
            assert provider.is_available() is True

    def test_is_available_when_server_down(self, provider: OllamaExtractionProvider) -> None:
        """Should return False when Ollama server is unreachable."""
        with patch.object(
            provider._client, "get", side_effect=httpx.ConnectError("Connection refused")
        ):
            assert provider.is_available() is False

    def test_is_available_when_model_not_found(self, provider: OllamaExtractionProvider) -> None:
        """Should return False when configured model is not available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.1:8b"}]}  # Different model

        with patch.object(provider._client, "get", return_value=mock_response):
            assert provider.is_available() is False


class TestOllamaExtraction:
    """Test invoice extraction functionality."""

    def test_extract_empty_text_returns_error(self, provider: OllamaExtractionProvider) -> None:
        """Should return error for empty OCR text."""
        result = provider.extract_invoice_fields("")
        assert result.success is False
        assert result.error == "Empty OCR text provided"
        assert result.provider == "ollama"

    def test_extract_whitespace_only_returns_error(
        self, provider: OllamaExtractionProvider
    ) -> None:
        """Should return error for whitespace-only OCR text."""
        result = provider.extract_invoice_fields("   \n\t  ")
        assert result.success is False
        assert result.error == "Empty OCR text provided"

    def test_extract_successful_response(self, provider: OllamaExtractionProvider) -> None:
        """Should parse valid JSON response from Ollama."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": json.dumps(
                {
                    "invoice_number": "12345",
                    "invoice_date": "2024-01-15",
                    "due_date": None,
                    "supplier_name": "Test Supplier",
                    "supplier_address": "123 Main St",
                    "customer_name": "Test Customer",
                    "subtotal": 100.0,
                    "tax_amount": 10.0,
                    "total_amount": 110.0,
                    "currency": "USD",
                }
            )
        }

        with patch.object(provider._client, "post", return_value=mock_response):
            result = provider.extract_invoice_fields("Invoice #12345...")
            assert result.success is True
            assert result.provider == "ollama"
            assert result.invoice_data is not None
            assert result.invoice_data.invoice_number == "12345"
            assert result.invoice_data.supplier_name == "Test Supplier"

    def test_extract_json_in_markdown_block(self, provider: OllamaExtractionProvider) -> None:
        """Should parse JSON wrapped in markdown code block."""
        json_data = {
            "invoice_number": "67890",
            "invoice_date": "2024-02-20",
            "total_amount": 500.0,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": f"```json\n{json.dumps(json_data)}\n```"}

        with patch.object(provider._client, "post", return_value=mock_response):
            result = provider.extract_invoice_fields("Invoice text...")
            assert result.success is True
            assert result.invoice_data is not None
            assert result.invoice_data.invoice_number == "67890"

    def test_extract_invalid_json_returns_error(self, provider: OllamaExtractionProvider) -> None:
        """Should return error when Ollama returns invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "This is not valid JSON"}

        with patch.object(provider._client, "post", return_value=mock_response):
            result = provider.extract_invoice_fields("Invoice text...")
            assert result.success is False
            assert "JSON parsing failed" in str(result.error)

    def test_extract_http_error_returns_error(self, provider: OllamaExtractionProvider) -> None:
        """Should return error when HTTP request fails."""
        with patch.object(
            provider._client,
            "post",
            side_effect=httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=MagicMock()
            ),
        ):
            result = provider.extract_invoice_fields("Invoice text...")
            assert result.success is False
            assert "Extraction failed" in str(result.error)


class TestJsonParsing:
    """Test JSON parsing helper method."""

    def test_parse_plain_json(self, provider: OllamaExtractionProvider) -> None:
        """Should parse plain JSON object."""
        response = '{"invoice_number": "123"}'
        result = provider._parse_json_response(response)
        assert result == {"invoice_number": "123"}

    def test_parse_json_in_markdown(self, provider: OllamaExtractionProvider) -> None:
        """Should extract JSON from markdown code block."""
        response = '```json\n{"invoice_number": "456"}\n```'
        result = provider._parse_json_response(response)
        assert result == {"invoice_number": "456"}

    def test_parse_json_with_surrounding_text(self, provider: OllamaExtractionProvider) -> None:
        """Should extract JSON even with surrounding text."""
        response = 'Here is the result: {"invoice_number": "789"} Done.'
        result = provider._parse_json_response(response)
        assert result == {"invoice_number": "789"}

    def test_parse_invalid_json_raises(self, provider: OllamaExtractionProvider) -> None:
        """Should raise JSONDecodeError for invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            provider._parse_json_response("not json at all")


class TestPromptBuilding:
    """Test prompt construction."""

    def test_prompt_contains_ocr_text(self, provider: OllamaExtractionProvider) -> None:
        """Prompt should include the OCR text."""
        ocr_text = "Invoice #12345 from Test Company"
        prompt = provider._build_extraction_prompt(ocr_text)
        assert ocr_text in prompt

    def test_prompt_contains_schema(self, provider: OllamaExtractionProvider) -> None:
        """Prompt should include JSON schema description."""
        prompt = provider._build_extraction_prompt("test")
        assert "invoice_number" in prompt
        assert "supplier_name" in prompt
        assert "total_amount" in prompt

    def test_prompt_contains_examples(self, provider: OllamaExtractionProvider) -> None:
        """Prompt should include few-shot examples."""
        prompt = provider._build_extraction_prompt("test")
        assert "EXAMPLES:" in prompt
        assert "Input:" in prompt
        assert "Output:" in prompt
