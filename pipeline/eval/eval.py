"""Evaluation harness for invoice extraction.

Runs the full extraction pipeline on gold dataset and computes metrics.
"""

import json
from pathlib import Path
from typing import Any

from pipeline.eval.metrics import evaluate_extraction
from services.extraction.schema import InvoiceData
from services.extraction.service import ExtractionService
from services.shared.config import get_settings


def load_gold_dataset(gold_file: Path) -> list[tuple[str, InvoiceData]]:
    """Load gold dataset from JSON file.

    Args:
        gold_file: Path to gold dataset JSON

    Returns:
        List of (ocr_text, expected_invoice_data) tuples
    """
    with open(gold_file) as f:
        data = json.load(f)

    samples = []
    for item in data:
        ocr_text = item["ocr_text"]
        expected_dict = item["expected"]

        # Convert expected dict to InvoiceData
        # Handle date conversion
        if expected_dict.get("invoice_date"):
            expected_dict["invoice_date"] = expected_dict["invoice_date"]
        if expected_dict.get("due_date"):
            expected_dict["due_date"] = expected_dict["due_date"]

        expected = InvoiceData(**expected_dict)
        samples.append((ocr_text, expected))

    return samples


def run_evaluation(gold_file: Path) -> dict[str, Any]:
    """Run evaluation on gold dataset.

    Args:
        gold_file: Path to gold dataset JSON file

    Returns:
        Evaluation results dict
    """
    # Load services
    settings = get_settings()
    extraction_service = ExtractionService(settings)

    # Load gold dataset
    samples = load_gold_dataset(gold_file)

    # Run extraction on all samples
    expected_list = []
    predicted_list = []

    for ocr_text, expected in samples:
        # Extract with LLM
        result = extraction_service.extract_invoice_fields(ocr_text)

        if result.success and result.invoice_data:
            predicted_list.append(result.invoice_data)
            expected_list.append(expected)
        else:
            # If extraction failed, create empty InvoiceData (all fields None)
            predicted_list.append(InvoiceData(**{}))
            expected_list.append(expected)

    # Evaluate
    report = evaluate_extraction(expected_list, predicted_list)

    # Format results
    results = {
        "total_samples": report.total_samples,
        "macro_f1": round(report.macro_f1, 4),
        "field_metrics": {
            field: {
                "precision": round(metrics.precision, 4),
                "recall": round(metrics.recall, 4),
                "f1": round(metrics.f1, 4),
                "support": metrics.support,
            }
            for field, metrics in report.field_metrics.items()
        },
    }

    return results


if __name__ == "__main__":
    # Run evaluation
    gold_file = Path("data/gold/invoices.json")
    results = run_evaluation(gold_file)

    # Print results
    print("\n" + "=" * 60)
    print("INVOICE EXTRACTION EVALUATION RESULTS")
    print("=" * 60)
    print(f"\nTotal Samples: {results['total_samples']}")
    print(f"Macro F1 Score: {results['macro_f1']:.1%}\n")

    print("Per-Field Metrics:")
    print("-" * 60)
    print(f"{'Field':<20} {'Precision':<12} {'Recall':<12} {'F1':<12}")
    print("-" * 60)

    for field, metrics in results["field_metrics"].items():
        print(
            f"{field:<20} {metrics['precision']:<12.1%} "
            f"{metrics['recall']:<12.1%} {metrics['f1']:<12.1%}"
        )

    print("=" * 60)
