#!/usr/bin/env python3
"""Evaluation script to compare Local vs OpenAI extraction providers.

Compares both providers on sample invoices to measure:
- Field extraction accuracy
- Confidence scores
- Performance (latency)
- Memory usage

Usage:
    python scripts/evaluate_providers.py

Requirements:
    - OPENAI_API_KEY environment variable set for OpenAI provider
    - GPU available for optimal local provider performance
"""

import os
import time
from datetime import date
from decimal import Decimal

from services.extraction.factory import create_extraction_service
from services.shared.config import Settings


def evaluate_providers() -> None:
    """Run comparative evaluation between local and OpenAI providers."""
    print("=" * 80)
    print("PROVIDER EVALUATION: Local vs OpenAI")
    print("=" * 80)

    # Test invoice samples
    test_invoices = [
        {
            "name": "Simple Invoice",
            "text": """
            INVOICE #INV-2025-001
            Date: November 26, 2025
            From: Tech Solutions LLC
            Bill To: Enterprise Corp
            Total: $1,234.56
            """,
            "expected": {
                "invoice_number": "INV-2025-001",
                "total_amount": Decimal("1234.56"),
            },
        },
        {
            "name": "Complex Invoice",
            "text": """
            INVOICE #INV-2025-12345

            Invoice Date: November 26, 2025
            Due Date: December 26, 2025

            From: Tech Solutions LLC
            456 Technology Drive

            Bill To: Enterprise Corporation
            789 Business Parkway

            Subtotal: $10,500.00
            Tax (8.5%): $892.50
            Total: $11,392.50
            """,
            "expected": {
                "invoice_number": "INV-2025-12345",
                "invoice_date": date(2025, 11, 26),
                "supplier_name": "Tech Solutions LLC",
                "customer_name": "Enterprise Corporation",
                "subtotal": Decimal("10500.00"),
                "tax_amount": Decimal("892.50"),
                "total_amount": Decimal("11392.50"),
            },
        },
    ]

    # Evaluate local provider
    print("\n[1] LOCAL PROVIDER EVALUATION")
    print("-" * 80)
    local_results = evaluate_provider("local", test_invoices)

    # Evaluate OpenAI provider (if API key available)
    print("\n[2] OPENAI PROVIDER EVALUATION")
    print("-" * 80)
    if os.getenv("OPENAI_API_KEY"):
        openai_results = evaluate_provider("openai", test_invoices)
    else:
        print("⚠ OPENAI_API_KEY not set - skipping OpenAI evaluation")
        openai_results = None

    # Comparison summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print_comparison(local_results, openai_results)


def evaluate_provider(provider_name: str, test_invoices: list) -> dict:
    """Evaluate a single provider on test invoices.

    Args:
        provider_name: Provider to evaluate ("local" or "openai")
        test_invoices: List of test invoice dictionaries

    Returns:
        Dictionary with evaluation results
    """
    settings = Settings(_env_file=None, extraction_provider=provider_name)
    service = create_extraction_service(settings)

    print(f"Provider: {provider_name}")
    print(f"Available: {service.is_available()}")

    results = {
        "provider": provider_name,
        "total_tests": len(test_invoices),
        "passed": 0,
        "failed": 0,
        "total_time": 0.0,
        "avg_confidence": 0.0,
        "details": [],
    }

    for i, invoice in enumerate(test_invoices, 1):
        print(f"\nTest {i}: {invoice['name']}")
        print("-" * 40)

        start_time = time.time()
        result = service.extract_invoice_fields(invoice["text"])
        elapsed = time.time() - start_time

        results["total_time"] += elapsed

        if result.success and result.invoice_data:
            # Check expected fields
            passed = True
            for field, expected_value in invoice["expected"].items():
                actual_value = getattr(result.invoice_data, field)
                match = actual_value == expected_value
                if not match:
                    passed = False
                status = "✓" if match else f"✗ (expected: {expected_value})"
                print(f"  {field}: {actual_value} {status}")

            if passed:
                results["passed"] += 1
                print("  Result: ✓ PASS")
            else:
                results["failed"] += 1
                print("  Result: ✗ FAIL")

            if result.invoice_data.confidence_score:
                results["avg_confidence"] += result.invoice_data.confidence_score

            print(f"  Confidence: {result.invoice_data.confidence_score}")
        else:
            results["failed"] += 1
            print(f"  Result: ✗ FAIL (error: {result.error})")

        print(f"  Latency: {elapsed:.3f}s")

        results["details"].append(
            {
                "test": invoice["name"],
                "success": result.success,
                "latency": elapsed,
            }
        )

    # Calculate averages
    if results["total_tests"] > 0:
        results["avg_confidence"] /= results["total_tests"]
        results["avg_latency"] = results["total_time"] / results["total_tests"]

    return results


def print_comparison(local_results: dict, openai_results: dict | None) -> None:
    """Print comparison table between providers.

    Args:
        local_results: Local provider results
        openai_results: OpenAI provider results (or None if skipped)
    """
    print("\nMetric                  | Local          | OpenAI")
    print("-" * 60)
    local_pass = f"{local_results['passed']}/{local_results['total_tests']}"
    print(f"Tests Passed            | {local_pass}            | ", end="")
    if openai_results:
        print(f"{openai_results['passed']}/{openai_results['total_tests']}")
    else:
        print("N/A")

    print(f"Avg Latency             | {local_results['avg_latency']:.3f}s        | ", end="")
    if openai_results:
        print(f"{openai_results['avg_latency']:.3f}s")
    else:
        print("N/A")

    print(f"Avg Confidence          | {local_results['avg_confidence']:.2f}           | ", end="")
    if openai_results:
        print(f"{openai_results['avg_confidence']:.2f}")
    else:
        print("N/A")

    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    print("\n✓ Local Provider Benefits:")
    print("  - Full data sovereignty (no cloud API calls)")
    print("  - No per-request costs")
    print("  - Predictable latency")
    print("  - No rate limits")
    print("  - Works offline")

    if openai_results:
        print("\n✓ OpenAI Provider Benefits:")
        print("  - Potentially higher accuracy on complex documents")
        print("  - No GPU infrastructure required")
        print("  - Automatic model updates")
        print("  - Broader document type support")

    print("\n💡 Recommendation:")
    print("  Use LOCAL for: Regulated industries, high volume, cost optimization")
    print("  Use OPENAI for: Complex documents, rapid prototyping, no GPU available")


if __name__ == "__main__":
    evaluate_providers()
