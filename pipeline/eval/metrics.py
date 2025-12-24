"""Evaluation metrics for invoice extraction.

Computes precision, recall, and F1 scores for extracted invoice fields.
Based on standard information extraction evaluation methodologies.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from services.extraction.schema import InvoiceData


@dataclass
class FieldMetrics:
    """Metrics for a single field."""

    precision: float
    recall: float
    f1: float
    support: int  # Number of samples


@dataclass
class EvaluationReport:
    """Complete evaluation report."""

    field_metrics: dict[str, FieldMetrics]
    macro_f1: float
    total_samples: int


def calculate_field_match(expected: Any, predicted: Any) -> bool:
    """Check if extracted field matches expected value.

    Args:
        expected: Ground truth value
        predicted: Extracted value

    Returns:
        True if values match (with tolerance for numeric fields)
    """
    # Both None
    if expected is None and predicted is None:
        return True

    # One is None
    if expected is None or predicted is None:
        return False

    # Numeric comparison (with small tolerance for floating point)
    if isinstance(expected, int | float | Decimal) and isinstance(predicted, int | float | Decimal):
        return abs(float(expected) - float(predicted)) < 0.01

    # Date comparison - handle string vs date object
    def normalize_date(val: Any) -> str | None:
        """Convert date or date string to YYYY-MM-DD string."""
        if isinstance(val, date):
            return val.isoformat()
        if isinstance(val, str):
            # Already in YYYY-MM-DD format or similar
            return val.strip()
        return None

    # Check if either value looks like a date (date object or YYYY-MM-DD string)
    is_expected_date = isinstance(expected, date) or (
        isinstance(expected, str) and len(expected) == 10 and expected[4:5] == "-"
    )
    is_predicted_date = isinstance(predicted, date) or (
        isinstance(predicted, str) and len(predicted) == 10 and str(predicted)[4:5] == "-"
    )

    if is_expected_date and is_predicted_date:
        exp_str = normalize_date(expected)
        pred_str = normalize_date(predicted)
        return exp_str == pred_str

    # String comparison (case-insensitive, stripped, normalized whitespace)
    if isinstance(expected, str) and isinstance(predicted, str):
        # Normalize: replace newlines with commas, collapse multiple spaces
        def normalize_string(s: str) -> str:
            s = s.strip().lower()
            s = s.replace("\n", ", ")  # Newlines to commas (common in addresses)
            s = " ".join(s.split())  # Collapse whitespace
            return s

        return normalize_string(expected) == normalize_string(predicted)

    # Direct comparison for other types
    return bool(expected == predicted)


def evaluate_extraction(
    expected: list[InvoiceData], predicted: list[InvoiceData]
) -> EvaluationReport:
    """Evaluate extraction accuracy against ground truth.

    Computes precision, recall, and F1 for each invoice field.
    Uses exact matching for structured fields.

    Args:
        expected: Ground truth invoice data
        predicted: Extracted invoice data

    Returns:
        Evaluation report with per-field and overall metrics
    """
    if len(expected) != len(predicted):
        raise ValueError("Expected and predicted lists must have same length")

    fields = [
        "invoice_number",
        "invoice_date",
        "due_date",
        "supplier_name",
        "supplier_address",
        "customer_name",
        "subtotal",
        "tax_amount",
        "total_amount",
        "currency",
    ]

    field_metrics: dict[str, FieldMetrics] = {}

    for field in fields:
        true_positives = 0
        false_positives = 0
        false_negatives = 0

        for exp, pred in zip(expected, predicted, strict=True):
            exp_value = getattr(exp, field)
            pred_value = getattr(pred, field)

            # True Positive: both have value and they match
            if exp_value is not None and pred_value is not None:
                if calculate_field_match(exp_value, pred_value):
                    true_positives += 1
                else:
                    false_positives += 1  # Predicted wrong value
                    false_negatives += 1  # Missed correct value

            # False Negative: expected value but got None
            elif exp_value is not None and pred_value is None:
                false_negatives += 1

            # False Positive: predicted value but should be None
            elif exp_value is None and pred_value is not None:
                false_positives += 1

            # True Negative: both None (not counted in metrics)

        # Calculate metrics
        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        field_metrics[field] = FieldMetrics(
            precision=precision,
            recall=recall,
            f1=f1,
            support=len(expected),
        )

    # Calculate macro F1 (average of all field F1 scores)
    macro_f1 = sum(m.f1 for m in field_metrics.values()) / len(field_metrics)

    return EvaluationReport(
        field_metrics=field_metrics,
        macro_f1=macro_f1,
        total_samples=len(expected),
    )
