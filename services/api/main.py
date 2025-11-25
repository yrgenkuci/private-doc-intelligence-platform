"""FastAPI application for document ingestion.

Production-ready API with:
- Health and readiness checks for Kubernetes
- File upload validation
- Async OCR processing
- Structured error responses
- Prometheus metrics for monitoring

Based on FastAPI best practices:
https://fastapi.tiangolo.com/
"""

import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel

from services.api import metrics
from services.ocr.service import OCRService
from services.shared.config import get_settings

settings = get_settings()
app = FastAPI(
    title="Document Intelligence Platform",
    description="Private document intelligence API for OCR and extraction",
    version=settings.service_version,
)

ocr_service = OCRService(settings)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Middleware to collect request metrics.

    Tracks:
    - Request count by method, endpoint, and status
    - Request duration by method and endpoint
    """
    # Skip metrics for /metrics endpoint itself
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Record metrics
    metrics.http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()

    metrics.http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)

    return response


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    service: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool


class UploadResponse(BaseModel):
    """Document upload response."""

    success: bool
    document_id: str
    text: str
    error: str | None = None


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """Health check endpoint for liveness probe.

    Returns:
        Health status information
    """
    return HealthResponse(
        status="healthy", version=settings.service_version, service=settings.service_name
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
def readiness_check() -> ReadinessResponse:
    """Readiness check endpoint for Kubernetes readiness probe.

    Returns:
        Readiness status
    """
    return ReadinessResponse(ready=True)


@app.get("/metrics", tags=["Monitoring"])
def get_metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns:
        Prometheus metrics in text format
    """
    metrics_data, content_type = metrics.get_metrics()
    return Response(content=metrics_data, media_type=content_type)


@app.post("/api/v1/documents/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
) -> UploadResponse:
    """Upload document for OCR processing.

    Args:
        file: Image file to process

    Returns:
        Upload response with extracted text

    Raises:
        HTTPException: If file is invalid or processing fails
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Only images are supported.",
        )

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    # Record upload size
    metrics.document_upload_size_bytes.observe(len(content))

    # Save to temp file for OCR processing
    doc_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Process with OCR
        ocr_start = time.time()
        result = ocr_service.extract_text(tmp_path)
        ocr_duration = time.time() - ocr_start

        # Record OCR metrics
        metrics.ocr_processing_duration_seconds.observe(ocr_duration)

        if not result.success:
            metrics.ocr_requests_total.labels(status="failed").inc()
            metrics.documents_uploaded_total.labels(status="failed").inc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OCR processing failed: {result.error}",
            )

        metrics.ocr_requests_total.labels(status="success").inc()
        metrics.documents_uploaded_total.labels(status="success").inc()

        return UploadResponse(success=True, document_id=doc_id, text=result.text)

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
