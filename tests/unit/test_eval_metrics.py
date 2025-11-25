"""Unit tests for evaluation metrics.

Tests cover:
- Field matching logic
- Metrics calculation (precision, recall, F1)
- Evaluation report generation
"""

from datetime import date
from decimal import Decimal

import pytest

from pipeline.eval.metrics import (
    EvaluationReport,
    FieldMetrics,
    calculate_field_match,
    evaluate_extraction,
)
from services.extraction.schema import InvoiceData


def test_calculate_field_match_strings() -> None:
    """Test string field matching (case-insensitive, stripped)."""
    assert calculate_field_match("TEST", "test") is True
    assert calculate_field_match("  test  ", "test") is True
    assert calculate_field_match("test", "different") is False


def test_calculate_field_match_numeric() -> None:
    """Test numeric field matching with tolerance."""
    assert calculate_field_match(100.0, 100.0) is True
    assert calculate_field_match(100.0, 100.005) is True  # Within tolerance
    assert calculate_field_match(Decimal("100.0"), 100.0) is True
    assert calculate_field_match(100.0, 200.0) is False


def test_calculate_field_match_dates() -> None:
    """Test date field matching."""
    assert calculate_field_match(date(2024, 1, 15), date(2024, 1, 15)) is True
    assert calculate_field_match(date(2024, 1, 15), date(2024, 1, 16)) is False


def test_calculate_field_match_none() -> None:
    """Test None field matching."""
    assert calculate_field_match(None, None) is True
    assert calculate_field_match(None, "value") is False
    assert calculate_field_match("value", None) is False


def test_evaluate_extraction_perfect() -> None:
    """Test evaluation with perfect extraction."""
    expected = [
        InvoiceData(
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 15),
            total_amount=Decimal("1000.00"),
            currency="USD",
        )
    ]
    predicted = [
        InvoiceData(
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 15),
            total_amount=Decimal("1000.00"),
            currency="USD",
        )
    ]

    report = evaluate_extraction(expected, predicted)

    # All matched fields should have perfect scores
    assert report.field_metrics["invoice_number"].precision == 1.0
    assert report.field_metrics["invoice_number"].recall == 1.0
    assert report.field_metrics["invoice_number"].f1 == 1.0


def test_evaluate_extraction_partial() -> None:
    """Test evaluation with partial extraction."""
    expected = [
        InvoiceData(
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 15),
            total_amount=Decimal("1000.00"),
        )
    ]
    predicted = [
        InvoiceData(
            invoice_number="INV-001",  # Correct
            invoice_date=date(2024, 1, 16),  # Wrong
            total_amount=None,  # Missing
        )
    ]

    report = evaluate_extraction(expected, predicted)

    # invoice_number: correct
    assert report.field_metrics["invoice_number"].f1 == 1.0

    # invoice_date: wrong
    assert report.field_metrics["invoice_date"].f1 == 0.0

    # total_amount: missing
    assert report.field_metrics["total_amount"].recall == 0.0


def test_evaluate_extraction_multiple_samples() -> None:
    """Test evaluation with multiple samples."""
    expected = [
        InvoiceData(invoice_number="INV-001", currency="USD"),
        InvoiceData(invoice_number="INV-002", currency="EUR"),
    ]
    predicted = [
        InvoiceData(invoice_number="INV-001", currency="USD"),  # Perfect
        InvoiceData(invoice_number="INV-999", currency="EUR"),  # Partial
    ]

    report = evaluate_extraction(expected, predicted)

    assert report.total_samples == 2
    # currency: 2/2 correct
    assert report.field_metrics["currency"].precision == 1.0
    # invoice_number: 1/2 correct
    assert report.field_metrics["invoice_number"].precision == 0.5


def test_evaluate_extraction_mismatched_lengths() -> None:
    """Test that mismatched list lengths raise error."""
    expected = [InvoiceData()]
    predicted = [InvoiceData(), InvoiceData()]

    with pytest.raises(ValueError, match="same length"):
        evaluate_extraction(expected, predicted)


def test_evaluation_report_structure() -> None:
    """Test EvaluationReport structure."""
    metrics = FieldMetrics(precision=0.9, recall=0.85, f1=0.875, support=10)
    report = EvaluationReport(
        field_metrics={"test_field": metrics}, macro_f1=0.875, total_samples=10
    )

    assert report.macro_f1 == 0.875
    assert report.total_samples == 10
    assert "test_field" in report.field_metrics
