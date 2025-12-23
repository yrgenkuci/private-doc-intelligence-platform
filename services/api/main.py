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

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel

from services.api import metrics
from services.extraction.factory import create_extraction_service
from services.extraction.schema import InvoiceData
from services.ocr.service import OCRService
from services.shared.config import get_settings
from services.storage.service import StorageService

settings = get_settings()
app = FastAPI(
    title="Document Intelligence Platform",
    description="Private document intelligence API for OCR and extraction",
    version=settings.service_version,
)

ocr_service = OCRService(settings)
extraction_service = create_extraction_service(settings)
storage_service = StorageService(settings)


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
    extracted_data: InvoiceData | None = None
    error: str | None = None
    storage_path: str | None = None


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
    file: UploadFile = File(..., description="Image file (PNG, JPEG, etc.)"),  # noqa: B008
    extract_fields: bool = Query(
        False,
        description="Enable LLM-powered structured field extraction (requires OPENAI_API_KEY)",
    ),
) -> UploadResponse:
    """Upload document for OCR processing and optional field extraction.

    This endpoint performs:
    1. **OCR (Optical Character Recognition)**: Extracts text from uploaded image
       using Tesseract
    2. **Field Extraction (optional)**: Extracts structured invoice fields using
       GPT-4o-mini

    ## Usage Examples

    **Basic OCR only:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/documents/upload" \\
      -F "file=@invoice.png"
    ```

    **OCR + Field Extraction:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/documents/upload?extract_fields=true" \\
      -F "file=@invoice.png"
    ```

    ## Requirements

    - **File Types**: PNG, JPEG, GIF, BMP, TIFF
    - **Max Size**: 10MB (configurable)
    - **LLM Extraction**: Requires `OPENAI_API_KEY` environment variable

    ## Response Fields

    - `success`: Always `true` if OCR succeeds
    - `document_id`: Unique identifier for this document
    - `text`: Raw OCR text extracted from the image
    - `extracted_data`: Structured invoice fields (null if not requested or extraction fails)

    ## Error Handling

    - Returns 400 if file is invalid, empty, or wrong type
    - Returns 500 if OCR processing fails
    - Returns 200 with `extracted_data: null` if OCR succeeds but LLM extraction fails

    Args:
        file: Image file to process (required)
        extract_fields: Enable LLM field extraction (optional, default: false)

    Returns:
        Upload response with OCR text and optionally structured invoice data

    Raises:
        HTTPException: If file is invalid or OCR processing fails
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

        # Extract structured fields if requested
        extracted_data = None
        if extract_fields:
            extraction_start = time.time()
            extraction_result = extraction_service.extract_invoice_fields(result.text)
            extraction_duration = time.time() - extraction_start

            # Record extraction metrics
            metrics.extraction_processing_duration_seconds.observe(extraction_duration)

            if extraction_result.success:
                extracted_data = extraction_result.invoice_data
                metrics.extraction_requests_total.labels(status="success").inc()
            else:
                metrics.extraction_requests_total.labels(status="failed").inc()
            # Note: If extraction fails, we still return OCR text successfully
            # This provides graceful degradation - OCR succeeded even if LLM failed

        # Store document in object storage if enabled
        storage_path = None
        if storage_service.is_available():
            file_ext = Path(file.filename).suffix if file.filename else ".bin"
            object_name = f"{doc_id}/original{file_ext}"
            storage_result = storage_service.upload_bytes(
                data=content,
                object_name=object_name,
                content_type=file.content_type,
            )
            if storage_result.success:
                storage_path = f"{storage_result.bucket}/{object_name}"
            # Note: Storage failure doesn't fail the request (graceful degradation)

        return UploadResponse(
            success=True,
            document_id=doc_id,
            text=result.text,
            extracted_data=extracted_data,
            storage_path=storage_path,
        )

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
