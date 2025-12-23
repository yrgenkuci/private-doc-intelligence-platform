"""Load external invoice dataset and convert to gold evaluation format.

Parses CSV files from external_invoices directory and converts to the
format expected by pipeline/eval/eval.py.

External dataset structure:
- CSV columns: File Name, Json Data, OCRed Text
- Json Data contains: invoice, items, subtotal, payment_instructions

Output format matches data/gold/invoices.json schema.
"""

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ExternalInvoiceRecord:
    """Parsed record from external CSV dataset."""

    file_name: str
    json_data: dict
    ocr_text: str


def parse_csv_file(csv_path: Path) -> list[ExternalInvoiceRecord]:
    """Parse a single CSV file from the external dataset.

    Args:
        csv_path: Path to CSV file

    Returns:
        List of ExternalInvoiceRecord objects

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    records: list[ExternalInvoiceRecord] = []

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate columns
        expected_columns = {"File Name", "Json Data", "OCRed Text"}
        if not expected_columns.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"CSV missing required columns. Expected: {expected_columns}, "
                f"Got: {reader.fieldnames}"
            )

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                json_data = json.loads(row["Json Data"])
                record = ExternalInvoiceRecord(
                    file_name=row["File Name"],
                    json_data=json_data,
                    ocr_text=row["OCRed Text"],
                )
                records.append(record)
            except json.JSONDecodeError as e:
                logger.warning(f"Row {row_num}: Invalid JSON, skipping. Error: {e}")
                continue

    logger.info(f"Parsed {len(records)} records from {csv_path.name}")
    return records


def parse_date(date_str: str) -> str | None:
    """Parse date string to ISO format (YYYY-MM-DD).

    Handles formats:
    - MM/DD/YYYY
    - YYYY-MM-DD (pass through)
    - Empty string

    Args:
        date_str: Date string to parse

    Returns:
        ISO format date string or None if invalid/empty
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Try MM/DD/YYYY format
    try:
        parsed = datetime.strptime(date_str, "%m/%d/%Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try YYYY-MM-DD format (pass through)
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    logger.debug(f"Could not parse date: {date_str}")
    return None


def parse_decimal(value_str: str) -> float | None:
    """Parse numeric string to float for JSON serialization.

    Handles both US format (1,234.56) and European format (1.234,56 or 234,56).

    Args:
        value_str: Numeric string (e.g., "232.95", "21.18", "360,58")

    Returns:
        Float value or None if invalid/empty
    """
    if not value_str or not value_str.strip():
        return None

    try:
        # Remove currency symbols
        cleaned = value_str.strip().replace("$", "").replace("€", "").replace("£", "")

        # Detect European format: comma as decimal separator
        # Pattern: digits,digits (where digits after comma is 1-2 chars, no period)
        # Examples: "360,58" "21,18" "1234,5"
        if "," in cleaned and "." not in cleaned:
            # Check if comma is decimal separator (1-2 digits after comma)
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2 and parts[1].isdigit():
                # European format: replace comma with period
                cleaned = cleaned.replace(",", ".")
            else:
                # US format with thousands separator: remove commas
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned and "." in cleaned:
            # Mixed format like "1,234.56" - remove comma (thousands separator)
            cleaned = cleaned.replace(",", "")
        # else: no comma, use as-is

        return float(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        logger.debug(f"Could not parse decimal: {value_str}")
        return None


def convert_to_gold_format(record: ExternalInvoiceRecord) -> dict:
    """Convert external record to gold dataset format.

    Maps external JSON fields to InvoiceData schema fields.

    Args:
        record: Parsed external invoice record

    Returns:
        Dict in gold dataset format with 'id', 'ocr_text', 'expected' keys
    """
    data = record.json_data
    invoice = data.get("invoice", {})
    subtotal = data.get("subtotal", {})
    payment = data.get("payment_instructions", {})

    # Parse financial values
    total = parse_decimal(subtotal.get("total", ""))
    tax = parse_decimal(subtotal.get("tax", ""))

    # Calculate subtotal (total - tax) if both present
    calculated_subtotal = None
    if total is not None and tax is not None:
        calculated_subtotal = round(total - tax, 2)

    # Parse dates - try invoice.due_date first, then payment_instructions.due_date
    due_date = parse_date(invoice.get("due_date", ""))
    if due_date is None:
        due_date = parse_date(payment.get("due_date", ""))

    expected = {
        "invoice_number": invoice.get("invoice_number") or None,
        "invoice_date": parse_date(invoice.get("invoice_date", "")),
        "due_date": due_date,
        "supplier_name": invoice.get("seller_name") or None,
        "supplier_address": invoice.get("seller_address") or None,
        "customer_name": invoice.get("client_name") or None,
        "subtotal": calculated_subtotal,
        "tax_amount": tax,
        "total_amount": total,
        "currency": "USD",  # Dataset doesn't specify currency
    }

    return {
        "id": record.file_name.replace(".jpg", "").replace(".png", ""),
        "ocr_text": record.ocr_text,
        "expected": expected,
    }


def load_external_dataset(data_dir: Path, limit: int | None = None) -> list[dict]:
    """Load and convert external dataset to gold format.

    Args:
        data_dir: Path to external_invoices directory
        limit: Optional limit on number of records to load

    Returns:
        List of dicts in gold dataset format
    """
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    logger.info(f"Found {len(csv_files)} CSV files in {data_dir}")

    all_records: list[dict] = []

    for csv_file in csv_files:
        records = parse_csv_file(csv_file)

        for record in records:
            gold_record = convert_to_gold_format(record)
            all_records.append(gold_record)

            if limit and len(all_records) >= limit:
                logger.info(f"Reached limit of {limit} records")
                return all_records

    logger.info(f"Total records loaded: {len(all_records)}")
    return all_records


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load external invoice dataset")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/external_invoices"),
        help="Path to external invoices directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/gold/invoices_external.json"),
        help="Output JSON file path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of records to load",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=0,
        help="Preview N records without saving",
    )

    args = parser.parse_args()

    # Load dataset
    records = load_external_dataset(args.data_dir, limit=args.limit or args.preview)

    if args.preview > 0:
        # Preview mode - just print sample records
        print(f"\n=== Preview of {min(args.preview, len(records))} records ===\n")
        for record in records[: args.preview]:
            print(json.dumps(record, indent=2))
            print("-" * 40)
    else:
        # Save to output file
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(records, f, indent=2)
        logger.info(f"Saved {len(records)} records to {args.output}")
