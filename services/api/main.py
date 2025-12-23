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

import json
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

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


# Async processing models
class AsyncUploadResponse(BaseModel):
    """Response for async document upload."""

    job_id: str
    document_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: str
    document_id: str
    ocr_text: str | None = None
    extracted_data: dict[str, Any] | None = None
    storage_path: str | None = None
    error: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


# Redis connection for async endpoints (lazy initialization)
_arq_pool: Any = None


async def get_arq_pool() -> Any:
    """Get or create arq Redis connection pool."""
    global _arq_pool
    if _arq_pool is None and settings.queue_enabled:
        from arq import create_pool
        from arq.connections import RedisSettings

        url = settings.redis_url
        if url.startswith("redis://"):
            url = url[8:]
        host_port = url.split("/")[0]
        host, port = host_port.split(":") if ":" in host_port else (host_port, "6379")
        db = int(url.split("/")[1]) if "/" in url else 0

        _arq_pool = await create_pool(RedisSettings(host=host, port=int(port), database=db))
    return _arq_pool


@app.post(
    "/api/v1/documents/upload/async",
    response_model=AsyncUploadResponse,
    tags=["Documents"],
)
async def upload_document_async(
    file: UploadFile = File(..., description="Image file (PNG, JPEG, etc.)"),  # noqa: B008
    extract_fields: bool = Query(
        False,
        description="Enable LLM-powered structured field extraction",
    ),
) -> AsyncUploadResponse:
    """Upload document for async background processing.

    This endpoint queues the document for background processing and
    returns immediately with a job ID for status tracking.

    ## Usage Examples

    **Submit for async processing:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/documents/upload/async" \\
      -F "file=@invoice.png"
    ```

    **Check job status:**
    ```bash
    curl "http://localhost:8000/api/v1/jobs/{job_id}"
    ```

    ## Requirements

    - Queue must be enabled (APP_QUEUE_ENABLED=true)
    - Redis must be running (APP_REDIS_URL)

    Args:
        file: Image file to process
        extract_fields: Enable LLM field extraction

    Returns:
        Job ID and status for tracking
    """
    if not settings.queue_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing is not enabled. Set APP_QUEUE_ENABLED=true",
        )

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

    # Generate IDs
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # Get arq pool
    pool = await get_arq_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue connection not available",
        )

    # Enqueue job

    await pool.enqueue_job(
        "process_document",
        job_id=job_id,
        document_id=doc_id,
        file_content=content,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        extract_fields=extract_fields,
    )

    # Store initial job status
    initial_status = {
        "job_id": job_id,
        "status": "pending",
        "document_id": doc_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    await pool.pool.set(f"job:{job_id}", json.dumps(initial_status), ex=86400)

    return AsyncUploadResponse(
        job_id=job_id,
        document_id=doc_id,
        status="pending",
        message="Document queued for processing",
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get status of an async processing job.

    Args:
        job_id: Job ID returned from async upload

    Returns:
        Current job status and results (if completed)
    """
    if not settings.queue_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing is not enabled",
        )

    pool = await get_arq_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue connection not available",
        )

    # Get job status from Redis
    job_data = await pool.pool.get(f"job:{job_id}")
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    job_dict = json.loads(job_data)
    return JobStatusResponse(**job_dict)


# Batch processing models
class BatchDocumentStatus(BaseModel):
    """Status of a single document in a batch."""

    document_id: str
    job_id: str
    filename: str
    status: str


class BatchUploadResponse(BaseModel):
    """Response for batch document upload."""

    batch_id: str
    total_documents: int
    status: str
    documents: list[BatchDocumentStatus]
    message: str


class BatchStatusResponse(BaseModel):
    """Response for batch status query."""

    batch_id: str
    total_documents: int
    completed: int
    failed: int
    pending: int
    status: str
    documents: list[JobStatusResponse]
    created_at: str | None = None


@app.post(
    "/api/v1/documents/upload/batch",
    response_model=BatchUploadResponse,
    tags=["Documents"],
)
async def upload_documents_batch(
    files: list[UploadFile] = File(..., description="Multiple image files"),  # noqa: B008
    extract_fields: bool = Query(
        False,
        description="Enable LLM-powered structured field extraction",
    ),
) -> BatchUploadResponse:
    """Upload multiple documents for batch background processing.

    This endpoint queues multiple documents for background processing
    and returns a batch ID for tracking all jobs.

    ## Usage Examples

    **Submit batch for processing:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/documents/upload/batch" \\
      -F "files=@invoice1.png" \\
      -F "files=@invoice2.png" \\
      -F "files=@invoice3.png"
    ```

    **Check batch status:**
    ```bash
    curl "http://localhost:8000/api/v1/batches/{batch_id}"
    ```

    ## Requirements

    - Queue must be enabled (APP_QUEUE_ENABLED=true)
    - Redis must be running (APP_REDIS_URL)
    - Maximum 100 files per batch

    Args:
        files: List of image files to process
        extract_fields: Enable LLM field extraction for all documents

    Returns:
        Batch ID and status for tracking
    """
    if not settings.queue_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing is not enabled. Set APP_QUEUE_ENABLED=true",
        )

    # Validate batch size
    max_batch_size = 100
    if len(files) > max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size exceeds maximum of {max_batch_size} files",
        )

    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    # Get arq pool
    pool = await get_arq_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue connection not available",
        )

    # Generate batch ID
    batch_id = str(uuid.uuid4())
    documents: list[BatchDocumentStatus] = []
    job_ids: list[str] = []

    # Process each file
    for file in files:
        # Validate file
        if not file.filename:
            continue

        if not file.content_type or not file.content_type.startswith("image/"):
            continue

        # Read content
        content = await file.read()
        if not content:
            continue

        # Generate IDs
        doc_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        job_ids.append(job_id)

        # Enqueue job
        await pool.enqueue_job(
            "process_document",
            job_id=job_id,
            document_id=doc_id,
            file_content=content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            extract_fields=extract_fields,
        )

        # Store initial job status
        initial_status = {
            "job_id": job_id,
            "status": "pending",
            "document_id": doc_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        await pool.pool.set(f"job:{job_id}", json.dumps(initial_status), ex=86400)

        documents.append(
            BatchDocumentStatus(
                document_id=doc_id,
                job_id=job_id,
                filename=file.filename,
                status="pending",
            )
        )

    if len(documents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid image files in batch",
        )

    # Store batch metadata
    batch_data = {
        "batch_id": batch_id,
        "job_ids": job_ids,
        "total_documents": len(documents),
        "created_at": datetime.utcnow().isoformat(),
    }
    await pool.pool.set(f"batch:{batch_id}", json.dumps(batch_data), ex=86400)

    return BatchUploadResponse(
        batch_id=batch_id,
        total_documents=len(documents),
        status="pending",
        documents=documents,
        message=f"Batch of {len(documents)} documents queued for processing",
    )


@app.get("/api/v1/batches/{batch_id}", response_model=BatchStatusResponse, tags=["Jobs"])
async def get_batch_status(batch_id: str) -> BatchStatusResponse:
    """Get status of a batch processing job.

    Returns aggregated status of all documents in the batch.

    Args:
        batch_id: Batch ID returned from batch upload

    Returns:
        Batch status with individual document statuses
    """
    if not settings.queue_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async processing is not enabled",
        )

    pool = await get_arq_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue connection not available",
        )

    # Get batch metadata
    batch_data = await pool.pool.get(f"batch:{batch_id}")
    if not batch_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )

    batch_dict = json.loads(batch_data)
    job_ids = batch_dict.get("job_ids", [])

    # Get status of all jobs
    documents: list[JobStatusResponse] = []
    completed = 0
    failed = 0
    pending = 0

    for job_id in job_ids:
        job_data = await pool.pool.get(f"job:{job_id}")
        if job_data:
            job_dict = json.loads(job_data)
            job_status = job_dict.get("status", "unknown")

            if job_status == "completed":
                completed += 1
            elif job_status == "failed":
                failed += 1
            else:
                pending += 1

            documents.append(JobStatusResponse(**job_dict))

    # Determine overall batch status
    if pending > 0:
        batch_status = "processing"
    elif failed > 0 and completed == 0:
        batch_status = "failed"
    elif failed > 0:
        batch_status = "partial"
    else:
        batch_status = "completed"

    return BatchStatusResponse(
        batch_id=batch_id,
        total_documents=len(job_ids),
        completed=completed,
        failed=failed,
        pending=pending,
        status=batch_status,
        documents=documents,
        created_at=batch_dict.get("created_at"),
    )
