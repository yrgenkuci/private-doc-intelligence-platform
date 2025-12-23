"""Unit tests for drift detection service.

Tests drift detection, alerting, and metrics.
"""

from decimal import Decimal

import pytest

from services.drift.service import DriftConfig, DriftDetector
from services.extraction.schema import InvoiceData


@pytest.fixture
def drift_config() -> DriftConfig:
    """Create test drift configuration."""
    return DriftConfig(
        window_size=50,
        min_samples=5,
        accuracy_threshold=0.80,
        drop_threshold=0.10,
        volatility_threshold=0.15,
        monitored_fields=["invoice_number", "total_amount", "supplier_name"],
    )


@pytest.fixture
def drift_detector(drift_config: DriftConfig) -> DriftDetector:
    """Create test drift detector."""
    return DriftDetector(drift_config)


@pytest.fixture
def sample_invoice() -> InvoiceData:
    """Create sample invoice data."""
    return InvoiceData(
        invoice_number="12345",
        total_amount=Decimal("100.00"),
        supplier_name="Test Corp",
    )


@pytest.fixture
def matching_expected() -> dict:
    """Create matching expected data."""
    return {
        "invoice_number": "12345",
        "total_amount": 100.00,
        "supplier_name": "Test Corp",
    }


@pytest.fixture
def mismatching_expected() -> dict:
    """Create mismatching expected data."""
    return {
        "invoice_number": "99999",
        "total_amount": 200.00,
        "supplier_name": "Other Corp",
    }


class TestDriftDetector:
    """Test DriftDetector class."""

    def test_init_default_config(self) -> None:
        """Should initialize with default config."""
        detector = DriftDetector()
        assert detector.config.window_size == 100
        assert detector.config.accuracy_threshold == 0.80

    def test_init_custom_config(self, drift_config: DriftConfig) -> None:
        """Should initialize with custom config."""
        detector = DriftDetector(drift_config)
        assert detector.config.window_size == 50
        assert detector.config.min_samples == 5

    def test_add_sample_no_expected(
        self, drift_detector: DriftDetector, sample_invoice: InvoiceData
    ) -> None:
        """Should add sample without expected data."""
        alerts = drift_detector.add_sample(
            document_id="doc-1",
            provider="test",
            predicted=sample_invoice,
            expected=None,
        )
        assert alerts == []
        assert len(drift_detector.samples) == 1

    def test_add_sample_with_expected(
        self,
        drift_detector: DriftDetector,
        sample_invoice: InvoiceData,
        matching_expected: dict,
    ) -> None:
        """Should calculate accuracy with expected data."""
        drift_detector.add_sample(
            document_id="doc-1",
            provider="test",
            predicted=sample_invoice,
            expected=matching_expected,
        )
        assert len(drift_detector.samples) == 1
        assert drift_detector.samples[0].overall_accuracy == 1.0

    def test_add_sample_mismatch(
        self,
        drift_detector: DriftDetector,
        sample_invoice: InvoiceData,
        mismatching_expected: dict,
    ) -> None:
        """Should detect mismatches in extraction."""
        drift_detector.add_sample(
            document_id="doc-1",
            provider="test",
            predicted=sample_invoice,
            expected=mismatching_expected,
        )
        assert drift_detector.samples[0].overall_accuracy == 0.0

    def test_threshold_breach_alert(
        self, drift_detector: DriftDetector, mismatching_expected: dict
    ) -> None:
        """Should trigger alert when accuracy below threshold."""
        # Add enough samples to trigger alerting
        bad_invoice = InvoiceData(
            invoice_number="wrong",
            total_amount=Decimal("0.00"),
            supplier_name="Wrong",
        )

        alerts = []
        for i in range(10):
            result = drift_detector.add_sample(
                document_id=f"doc-{i}",
                provider="test",
                predicted=bad_invoice,
                expected=mismatching_expected,
            )
            alerts.extend(result)

        # Should have threshold breach alerts
        threshold_alerts = [a for a in alerts if a.alert_type == "threshold_breach"]
        assert len(threshold_alerts) > 0

    def test_accuracy_drop_alert(
        self,
        drift_detector: DriftDetector,
        sample_invoice: InvoiceData,
        matching_expected: dict,
        mismatching_expected: dict,
    ) -> None:
        """Should trigger alert when accuracy drops from baseline."""
        # Set baseline
        drift_detector.set_baseline(0.90)

        # Add perfect samples first
        for i in range(5):
            drift_detector.add_sample(
                document_id=f"good-{i}",
                provider="test",
                predicted=sample_invoice,
                expected=matching_expected,
            )

        # Now add bad samples
        bad_invoice = InvoiceData(
            invoice_number="wrong",
            total_amount=Decimal("0.00"),
            supplier_name="Wrong",
        )

        alerts = []
        for i in range(10):
            result = drift_detector.add_sample(
                document_id=f"bad-{i}",
                provider="test",
                predicted=bad_invoice,
                expected=mismatching_expected,
            )
            alerts.extend(result)

        # Should have accuracy drop alert
        drop_alerts = [a for a in alerts if a.alert_type == "accuracy_drop"]
        assert len(drop_alerts) > 0

    def test_get_stats_empty(self, drift_detector: DriftDetector) -> None:
        """Should return stats for empty detector."""
        stats = drift_detector.get_stats()
        assert stats["sample_count"] == 0
        assert stats["rolling_accuracy"] is None

    def test_get_stats_with_samples(
        self,
        drift_detector: DriftDetector,
        sample_invoice: InvoiceData,
        matching_expected: dict,
    ) -> None:
        """Should return stats with samples."""
        for i in range(10):
            drift_detector.add_sample(
                document_id=f"doc-{i}",
                provider="test",
                predicted=sample_invoice,
                expected=matching_expected,
            )

        stats = drift_detector.get_stats()
        assert stats["sample_count"] == 10
        assert stats["rolling_accuracy"] == 1.0

    def test_set_baseline(self, drift_detector: DriftDetector) -> None:
        """Should set baseline accuracy."""
        drift_detector.set_baseline(0.85)
        assert drift_detector.baseline_accuracy == 0.85

    def test_clear(
        self,
        drift_detector: DriftDetector,
        sample_invoice: InvoiceData,
        matching_expected: dict,
    ) -> None:
        """Should clear all data."""
        # Add samples
        for i in range(5):
            drift_detector.add_sample(
                document_id=f"doc-{i}",
                provider="test",
                predicted=sample_invoice,
                expected=matching_expected,
            )

        assert len(drift_detector.samples) == 5

        drift_detector.clear()

        assert len(drift_detector.samples) == 0
        assert len(drift_detector.alerts) == 0

    def test_window_size_limit(
        self,
        drift_config: DriftConfig,
        sample_invoice: InvoiceData,
        matching_expected: dict,
    ) -> None:
        """Should respect window size limit."""
        config = DriftConfig(window_size=10)
        detector = DriftDetector(config)

        # Add more than window size
        for i in range(20):
            detector.add_sample(
                document_id=f"doc-{i}",
                provider="test",
                predicted=sample_invoice,
                expected=matching_expected,
            )

        # Should only keep last 10
        assert len(detector.samples) == 10


class TestDriftConfig:
    """Test DriftConfig class."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        config = DriftConfig()
        assert config.window_size == 100
        assert config.min_samples == 20
        assert config.accuracy_threshold == 0.80
        assert config.drop_threshold == 0.10
        assert "invoice_number" in config.monitored_fields

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = DriftConfig(
            window_size=50,
            accuracy_threshold=0.90,
            monitored_fields=["custom_field"],
        )
        assert config.window_size == 50
        assert config.accuracy_threshold == 0.90
        assert config.monitored_fields == ["custom_field"]
