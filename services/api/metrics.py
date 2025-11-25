"""Prometheus metrics for API service.

Exposes key metrics for monitoring:
- Request counts by endpoint and status
- Request duration histograms
- Document upload metrics
- OCR processing metrics

Based on Prometheus best practices:
https://prometheus.io/docs/practices/naming/
"""

from prometheus_client import Counter, Histogram, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Document processing metrics
documents_uploaded_total = Counter(
    "documents_uploaded_total",
    "Total documents uploaded",
    ["status"],  # success, failed
)

document_upload_size_bytes = Histogram(
    "document_upload_size_bytes",
    "Document upload size in bytes",
    buckets=(1024, 10240, 102400, 1048576, 10485760),  # 1KB to 10MB
)

# OCR processing metrics
ocr_processing_duration_seconds = Histogram(
    "ocr_processing_duration_seconds",
    "OCR processing duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

ocr_requests_total = Counter(
    "ocr_requests_total",
    "Total OCR processing requests",
    ["status"],  # success, failed
)


def get_metrics() -> tuple[bytes, str]:
    """Generate Prometheus metrics in text format.

    Returns:
        Tuple of (metrics bytes, content type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST
