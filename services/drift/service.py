"""Drift detection service for monitoring extraction accuracy.

Tracks extraction accuracy over time and detects when performance
degrades below acceptable thresholds.

Industry standard approach based on:
- ML Model Monitoring best practices
- Statistical Process Control (SPC)
- Production ML systems patterns (Google, Netflix, Uber)
"""

import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from statistics import mean, stdev
from typing import Any

from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel

from pipeline.eval.metrics import calculate_field_match
from services.extraction.schema import InvoiceData

logger = logging.getLogger(__name__)


# Prometheus metrics for drift detection
drift_samples_total = Counter(
    "extraction_drift_samples_total",
    "Total number of samples used for drift detection",
    ["provider"],
)

drift_accuracy_gauge = Gauge(
    "extraction_drift_accuracy",
    "Current rolling accuracy for extraction",
    ["provider", "field"],
)

drift_alerts_total = Counter(
    "extraction_drift_alerts_total",
    "Total number of drift alerts triggered",
    ["provider", "alert_type"],
)

drift_f1_histogram = Histogram(
    "extraction_drift_f1_score",
    "Distribution of F1 scores for drift monitoring",
    ["provider"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0],
)


@dataclass
class DriftAlert:
    """Represents a drift alert."""

    alert_type: str  # accuracy_drop, threshold_breach, volatility
    provider: str
    field: str | None
    current_value: float
    threshold: float
    message: str
    timestamp: datetime


class DriftSample(BaseModel):
    """A single sample for drift detection."""

    document_id: str
    provider: str
    predicted: dict[str, Any]
    expected: dict[str, Any] | None
    field_matches: dict[str, bool]
    overall_accuracy: float
    timestamp: datetime


class DriftConfig(BaseModel):
    """Configuration for drift detection."""

    # Window size for rolling metrics
    window_size: int = 100

    # Minimum samples before alerting
    min_samples: int = 20

    # Accuracy threshold (alert if below)
    accuracy_threshold: float = 0.80

    # Drop threshold (alert if accuracy drops by this percentage)
    drop_threshold: float = 0.10

    # Volatility threshold (alert if std dev exceeds this)
    volatility_threshold: float = 0.15

    # Fields to monitor
    monitored_fields: list[str] = [
        "invoice_number",
        "invoice_date",
        "supplier_name",
        "total_amount",
    ]


class DriftDetector:
    """Detects accuracy drift in extraction models.

    Uses a sliding window approach to track accuracy metrics
    and detect significant performance degradation.

    Attributes:
        config: Drift detection configuration
        samples: Deque of recent samples (bounded by window_size)
        baseline_accuracy: Established baseline accuracy
        alerts: List of triggered alerts
    """

    def __init__(self, config: DriftConfig | None = None) -> None:
        """Initialize drift detector.

        Args:
            config: Configuration for drift detection
        """
        self.config = config or DriftConfig()
        self.samples: deque[DriftSample] = deque(maxlen=self.config.window_size)
        self.baseline_accuracy: float | None = None
        self.alerts: list[DriftAlert] = []
        self._field_accuracies: dict[str, deque[float]] = {
            field: deque(maxlen=self.config.window_size) for field in self.config.monitored_fields
        }

    def add_sample(
        self,
        document_id: str,
        provider: str,
        predicted: InvoiceData,
        expected: dict[str, Any] | None = None,
    ) -> list[DriftAlert]:
        """Add a sample and check for drift.

        Args:
            document_id: Unique document identifier
            provider: Extraction provider name
            predicted: Predicted invoice data
            expected: Ground truth data (optional)

        Returns:
            List of triggered alerts (empty if no drift detected)
        """
        # Convert predicted to dict for comparison
        predicted_dict = self._invoice_to_dict(predicted)

        # Calculate field matches
        field_matches: dict[str, bool] = {}
        overall_matches = 0
        total_fields = 0

        for field in self.config.monitored_fields:
            pred_value = predicted_dict.get(field)
            exp_value = expected.get(field) if expected else None

            if expected and exp_value is not None:
                match = calculate_field_match(exp_value, pred_value)
                field_matches[field] = match
                if match:
                    overall_matches += 1
                total_fields += 1

                # Track field-level accuracy
                self._field_accuracies[field].append(1.0 if match else 0.0)

        # Calculate overall accuracy for this sample
        overall_accuracy = overall_matches / total_fields if total_fields > 0 else 0.0

        # Create sample
        sample = DriftSample(
            document_id=document_id,
            provider=provider,
            predicted=predicted_dict,
            expected=expected,
            field_matches=field_matches,
            overall_accuracy=overall_accuracy,
            timestamp=datetime.now(UTC),
        )

        self.samples.append(sample)

        # Update metrics
        drift_samples_total.labels(provider=provider).inc()
        drift_f1_histogram.labels(provider=provider).observe(overall_accuracy)

        # Check for drift
        return self._check_drift(provider)

    def _check_drift(self, provider: str) -> list[DriftAlert]:
        """Check for drift conditions.

        Args:
            provider: Extraction provider name

        Returns:
            List of triggered alerts
        """
        triggered_alerts: list[DriftAlert] = []

        # Need minimum samples
        if len(self.samples) < self.config.min_samples:
            return triggered_alerts

        # Calculate rolling accuracy
        recent_accuracies = [s.overall_accuracy for s in self.samples]
        rolling_accuracy = mean(recent_accuracies)

        # Update gauge
        drift_accuracy_gauge.labels(provider=provider, field="overall").set(rolling_accuracy)

        # Check threshold breach
        if rolling_accuracy < self.config.accuracy_threshold:
            alert = DriftAlert(
                alert_type="threshold_breach",
                provider=provider,
                field=None,
                current_value=rolling_accuracy,
                threshold=self.config.accuracy_threshold,
                message=(
                    f"Extraction accuracy ({rolling_accuracy:.2%}) below "
                    f"threshold ({self.config.accuracy_threshold:.2%})"
                ),
                timestamp=datetime.now(UTC),
            )
            triggered_alerts.append(alert)
            drift_alerts_total.labels(provider=provider, alert_type="threshold_breach").inc()
            logger.warning(alert.message)

        # Check for accuracy drop from baseline
        if self.baseline_accuracy is not None:
            drop = self.baseline_accuracy - rolling_accuracy
            if drop > self.config.drop_threshold:
                alert = DriftAlert(
                    alert_type="accuracy_drop",
                    provider=provider,
                    field=None,
                    current_value=rolling_accuracy,
                    threshold=self.baseline_accuracy - self.config.drop_threshold,
                    message=(
                        f"Accuracy dropped {drop:.2%} from baseline "
                        f"({self.baseline_accuracy:.2%} -> {rolling_accuracy:.2%})"
                    ),
                    timestamp=datetime.now(UTC),
                )
                triggered_alerts.append(alert)
                drift_alerts_total.labels(provider=provider, alert_type="accuracy_drop").inc()
                logger.warning(alert.message)

        # Check volatility
        if len(recent_accuracies) >= 10:
            volatility = stdev(recent_accuracies)
            if volatility > self.config.volatility_threshold:
                alert = DriftAlert(
                    alert_type="volatility",
                    provider=provider,
                    field=None,
                    current_value=volatility,
                    threshold=self.config.volatility_threshold,
                    message=(f"High accuracy volatility detected " f"(std dev: {volatility:.2%})"),
                    timestamp=datetime.now(UTC),
                )
                triggered_alerts.append(alert)
                drift_alerts_total.labels(provider=provider, alert_type="volatility").inc()
                logger.warning(alert.message)

        # Check per-field accuracy
        for field in self.config.monitored_fields:
            field_samples = list(self._field_accuracies[field])
            if len(field_samples) >= self.config.min_samples:
                field_accuracy = mean(field_samples)
                drift_accuracy_gauge.labels(provider=provider, field=field).set(field_accuracy)

                if field_accuracy < self.config.accuracy_threshold:
                    alert = DriftAlert(
                        alert_type="field_threshold_breach",
                        provider=provider,
                        field=field,
                        current_value=field_accuracy,
                        threshold=self.config.accuracy_threshold,
                        message=(
                            f"Field '{field}' accuracy ({field_accuracy:.2%}) " f"below threshold"
                        ),
                        timestamp=datetime.now(UTC),
                    )
                    triggered_alerts.append(alert)
                    drift_alerts_total.labels(
                        provider=provider, alert_type="field_threshold_breach"
                    ).inc()
                    logger.warning(alert.message)

        self.alerts.extend(triggered_alerts)
        return triggered_alerts

    def set_baseline(self, accuracy: float) -> None:
        """Set the baseline accuracy for drift comparison.

        Args:
            accuracy: Baseline accuracy (0.0 to 1.0)
        """
        self.baseline_accuracy = accuracy
        logger.info(f"Drift baseline set to {accuracy:.2%}")

    def get_stats(self) -> dict[str, Any]:
        """Get current drift detection statistics.

        Returns:
            Dictionary of statistics
        """
        if len(self.samples) == 0:
            return {
                "sample_count": 0,
                "rolling_accuracy": None,
                "baseline_accuracy": self.baseline_accuracy,
                "alerts_count": len(self.alerts),
            }

        recent_accuracies = [s.overall_accuracy for s in self.samples]

        return {
            "sample_count": len(self.samples),
            "rolling_accuracy": mean(recent_accuracies),
            "accuracy_std_dev": (stdev(recent_accuracies) if len(recent_accuracies) > 1 else 0.0),
            "baseline_accuracy": self.baseline_accuracy,
            "min_accuracy": min(recent_accuracies),
            "max_accuracy": max(recent_accuracies),
            "alerts_count": len(self.alerts),
            "recent_alerts": [
                {
                    "type": a.alert_type,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.alerts[-5:]
            ],
        }

    def _invoice_to_dict(self, invoice: InvoiceData) -> dict[str, Any]:
        """Convert InvoiceData to dict for comparison."""
        result: dict[str, Any] = {}
        for field in self.config.monitored_fields:
            value = getattr(invoice, field, None)
            if isinstance(value, Decimal):
                result[field] = float(value)
            else:
                result[field] = value
        return result

    def clear(self) -> None:
        """Clear all samples and alerts."""
        self.samples.clear()
        self.alerts.clear()
        for field_deque in self._field_accuracies.values():
            field_deque.clear()
        logger.info("Drift detector cleared")
