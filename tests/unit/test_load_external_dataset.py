"""Unit tests for external dataset loader.

Tests cover:
- Date parsing (multiple formats)
- Decimal parsing
- CSV record parsing
- Field mapping to gold format
"""

import tempfile
from pathlib import Path

import pytest

from scripts.load_external_dataset import (
    ExternalInvoiceRecord,
    convert_to_gold_format,
    parse_csv_file,
    parse_date,
    parse_decimal,
)

# --- Date Parsing Tests ---


def test_parse_date_mm_dd_yyyy() -> None:
    """Test parsing MM/DD/YYYY format."""
    assert parse_date("02/23/2021") == "2021-02-23"
    assert parse_date("12/31/2024") == "2024-12-31"
    assert parse_date("01/01/2020") == "2020-01-01"


def test_parse_date_yyyy_mm_dd() -> None:
    """Test parsing YYYY-MM-DD format (pass through)."""
    assert parse_date("2021-02-23") == "2021-02-23"
    assert parse_date("2024-12-31") == "2024-12-31"


def test_parse_date_empty() -> None:
    """Test parsing empty or None date values."""
    assert parse_date("") is None
    assert parse_date("   ") is None


def test_parse_date_invalid() -> None:
    """Test parsing invalid date formats returns None."""
    assert parse_date("not-a-date") is None
    assert parse_date("2021/02/23") is None  # Wrong separator
    assert parse_date("23-02-2021") is None  # DD-MM-YYYY not supported


# --- Decimal Parsing Tests ---


def test_parse_decimal_simple() -> None:
    """Test parsing simple decimal strings."""
    assert parse_decimal("232.95") == 232.95
    assert parse_decimal("21.18") == 21.18
    assert parse_decimal("0.00") == 0.0


def test_parse_decimal_with_commas() -> None:
    """Test parsing decimals with thousand separators (US format)."""
    assert parse_decimal("1,234.56") == 1234.56
    assert parse_decimal("10,000.00") == 10000.0


def test_parse_decimal_european_format() -> None:
    """Test parsing European format (comma as decimal separator)."""
    assert parse_decimal("360,58") == 360.58
    assert parse_decimal("32,78") == 32.78
    assert parse_decimal("211,77") == 211.77
    assert parse_decimal("1234,5") == 1234.5


def test_parse_decimal_with_currency() -> None:
    """Test parsing decimals with currency symbols."""
    assert parse_decimal("$232.95") == 232.95
    assert parse_decimal("$ 100.00") == 100.0


def test_parse_decimal_empty() -> None:
    """Test parsing empty decimal values."""
    assert parse_decimal("") is None
    assert parse_decimal("   ") is None


def test_parse_decimal_invalid() -> None:
    """Test parsing invalid decimal values."""
    assert parse_decimal("not-a-number") is None
    assert parse_decimal("abc") is None


# --- CSV Parsing Tests ---


def test_parse_csv_file_valid() -> None:
    """Test parsing valid CSV file."""
    json_data = (
        '{"invoice": {"invoice_number": "123", "invoice_date": "01/15/2024", '
        '"due_date": "", "seller_name": "Acme", "seller_address": "123 Main", '
        '"client_name": "Customer"}, "subtotal": {"tax": "10.00", "total": "110.00"}, '
        '"payment_instructions": {}}'
    )
    # CSV uses double quotes to escape quotes inside fields
    escaped_json = json_data.replace('"', '""')
    csv_content = f'File Name,Json Data,OCRed Text\ntest-001.jpg,"{escaped_json}",Sample OCR text\n'

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        csv_path = Path(f.name)

    try:
        records = parse_csv_file(csv_path)
        assert len(records) == 1
        assert records[0].file_name == "test-001.jpg"
        assert records[0].ocr_text == "Sample OCR text"
        assert records[0].json_data["invoice"]["invoice_number"] == "123"
    finally:
        csv_path.unlink()


def test_parse_csv_file_not_found() -> None:
    """Test parsing non-existent CSV file raises error."""
    with pytest.raises(FileNotFoundError):
        parse_csv_file(Path("/nonexistent/file.csv"))


def test_parse_csv_file_invalid_columns() -> None:
    """Test parsing CSV with missing columns raises error."""
    csv_content = "Wrong,Columns,Here\n1,2,3\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        csv_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="missing required columns"):
            parse_csv_file(csv_path)
    finally:
        csv_path.unlink()


def test_parse_csv_file_invalid_json_skipped() -> None:
    """Test that rows with invalid JSON are skipped."""
    valid_json = (
        '{"invoice": {"invoice_number": "456"}, "subtotal": {}, "payment_instructions": {}}'
    )
    escaped_json = valid_json.replace('"', '""')
    csv_content = (
        "File Name,Json Data,OCRed Text\n"
        'test-001.jpg,"{invalid json}",Text 1\n'
        f'test-002.jpg,"{escaped_json}",Text 2\n'
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        csv_path = Path(f.name)

    try:
        records = parse_csv_file(csv_path)
        # Only valid row should be parsed
        assert len(records) == 1
        assert records[0].file_name == "test-002.jpg"
    finally:
        csv_path.unlink()


# --- Gold Format Conversion Tests ---


def test_convert_to_gold_format_complete() -> None:
    """Test converting complete invoice record to gold format."""
    record = ExternalInvoiceRecord(
        file_name="invoice-001.jpg",
        json_data={
            "invoice": {
                "invoice_number": "INV-123",
                "invoice_date": "02/15/2024",
                "due_date": "03/15/2024",
                "seller_name": "Supplier Co",
                "seller_address": "123 Supplier St",
                "client_name": "Customer Inc",
                "client_address": "456 Customer Ave",
            },
            "subtotal": {"tax": "50.00", "total": "550.00", "discount": ""},
            "payment_instructions": {},
        },
        ocr_text="Sample invoice text",
    )

    result = convert_to_gold_format(record)

    assert result["id"] == "invoice-001"
    assert result["ocr_text"] == "Sample invoice text"
    assert result["expected"]["invoice_number"] == "INV-123"
    assert result["expected"]["invoice_date"] == "2024-02-15"
    assert result["expected"]["due_date"] == "2024-03-15"
    assert result["expected"]["supplier_name"] == "Supplier Co"
    assert result["expected"]["supplier_address"] == "123 Supplier St"
    assert result["expected"]["customer_name"] == "Customer Inc"
    assert result["expected"]["tax_amount"] == 50.0
    assert result["expected"]["total_amount"] == 550.0
    assert result["expected"]["subtotal"] == 500.0  # total - tax
    assert result["expected"]["currency"] == "USD"


def test_convert_to_gold_format_missing_due_date() -> None:
    """Test conversion when due_date is empty."""
    record = ExternalInvoiceRecord(
        file_name="test.jpg",
        json_data={
            "invoice": {
                "invoice_number": "123",
                "invoice_date": "01/01/2024",
                "due_date": "",
                "seller_name": "Seller",
                "seller_address": "",
                "client_name": "Client",
            },
            "subtotal": {"tax": "10", "total": "100"},
            "payment_instructions": {"due_date": ""},
        },
        ocr_text="text",
    )

    result = convert_to_gold_format(record)
    assert result["expected"]["due_date"] is None


def test_convert_to_gold_format_due_date_fallback() -> None:
    """Test due_date fallback to payment_instructions."""
    record = ExternalInvoiceRecord(
        file_name="test.jpg",
        json_data={
            "invoice": {
                "invoice_number": "123",
                "invoice_date": "01/01/2024",
                "due_date": "",
                "seller_name": "Seller",
                "seller_address": "",
                "client_name": "Client",
            },
            "subtotal": {"tax": "10", "total": "100"},
            "payment_instructions": {"due_date": "02/01/2024"},
        },
        ocr_text="text",
    )

    result = convert_to_gold_format(record)
    assert result["expected"]["due_date"] == "2024-02-01"


def test_convert_to_gold_format_strips_extension() -> None:
    """Test that file extensions are stripped from ID."""
    record = ExternalInvoiceRecord(
        file_name="batch1-0001.jpg",
        json_data={
            "invoice": {},
            "subtotal": {},
            "payment_instructions": {},
        },
        ocr_text="text",
    )

    result = convert_to_gold_format(record)
    assert result["id"] == "batch1-0001"
    assert ".jpg" not in result["id"]


def test_convert_to_gold_format_empty_values_as_none() -> None:
    """Test that empty string values become None."""
    record = ExternalInvoiceRecord(
        file_name="test.jpg",
        json_data={
            "invoice": {
                "invoice_number": "",
                "invoice_date": "",
                "due_date": "",
                "seller_name": "",
                "seller_address": "",
                "client_name": "",
            },
            "subtotal": {"tax": "", "total": ""},
            "payment_instructions": {},
        },
        ocr_text="text",
    )

    result = convert_to_gold_format(record)
    assert result["expected"]["invoice_number"] is None
    assert result["expected"]["invoice_date"] is None
    assert result["expected"]["tax_amount"] is None
    assert result["expected"]["total_amount"] is None
