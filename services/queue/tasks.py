"""Async task definitions for document processing.

Uses arq (async Redis queue) for background task processing.
Implements document OCR and extraction as background jobs.

Based on arq documentation:
https://arq-docs.helpmanual.io/
"""

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from services.extraction.factory import create_extraction_service
from services.ocr.service import OCRService
from services.shared.config import Settings, get_settings
from services.storage.service import StorageService

logger = logging.getLogger(__name__)


class JobResult(BaseModel):
    """Result of a background job.

    Attributes:
        job_id: Unique job identifier
        status: Job status (pending, processing, completed, failed)
        document_id: Document ID being processed
        ocr_text: Extracted OCR text (if completed)
        extracted_data: Structured data (if extraction requested)
        storage_path: Path in object storage (if stored)
        error: Error message (if failed)
        created_at: Job creation timestamp
        completed_at: Job completion timestamp
    """

    job_id: str
    status: str
    document_id: str
    ocr_text: str | None = None
    extracted_data: dict[str, Any] | None = None
    storage_path: str | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


async def process_document(
    ctx: dict[str, Any],
    job_id: str,
    document_id: str,
    file_content: bytes,
    filename: str,
    content_type: str,
    extract_fields: bool = False,
) -> dict[str, Any]:
    """Process document with OCR and optional extraction.

    This task runs in the background worker and performs:
    1. Save file to temp location
    2. Run OCR to extract text
    3. Optionally run LLM extraction
    4. Store results in object storage (if enabled)
    5. Return results

    Args:
        ctx: arq context (contains redis connection)
        job_id: Unique job identifier
        document_id: Document ID
        file_content: Raw file bytes
        filename: Original filename
        content_type: MIME type
        extract_fields: Whether to run LLM extraction

    Returns:
        JobResult as dict
    """
    logger.info(f"Processing document job {job_id} for document {document_id}")

    settings: Settings = ctx.get("settings", get_settings())
    ocr_service: OCRService = ctx.get("ocr_service", OCRService(settings))
    extraction_service = ctx.get("extraction_service", create_extraction_service(settings))
    storage_service: StorageService = ctx.get("storage_service", StorageService(settings))
    redis = ctx["redis"]

    result = JobResult(
        job_id=job_id,
        status="processing",
        document_id=document_id,
        created_at=datetime.utcnow().isoformat(),
    )

    # Update status in Redis
    await redis.set(f"job:{job_id}", result.model_dump_json(), ex=86400)  # 24h TTL

    try:
        # Save to temp file
        suffix = Path(filename).suffix if filename else ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)

        try:
            # Run OCR
            logger.info(f"Running OCR for job {job_id}")
            ocr_result = ocr_service.extract_text(tmp_path)

            if not ocr_result.success:
                result.status = "failed"
                result.error = f"OCR failed: {ocr_result.error}"
                result.completed_at = datetime.utcnow().isoformat()
                await redis.set(f"job:{job_id}", result.model_dump_json(), ex=86400)
                return result.model_dump()

            result.ocr_text = ocr_result.text

            # Run extraction if requested
            if extract_fields:
                logger.info(f"Running extraction for job {job_id}")
                extraction_result = extraction_service.extract_invoice_fields(ocr_result.text)
                if extraction_result.success and extraction_result.invoice_data:
                    result.extracted_data = json.loads(
                        extraction_result.invoice_data.model_dump_json()
                    )

            # Store in object storage if enabled
            if storage_service.is_available():
                logger.info(f"Storing document for job {job_id}")
                object_name = f"{document_id}/original{suffix}"
                storage_result = storage_service.upload_bytes(
                    data=file_content,
                    object_name=object_name,
                    content_type=content_type,
                )
                if storage_result.success:
                    result.storage_path = f"{storage_result.bucket}/{object_name}"

            result.status = "completed"
            result.completed_at = datetime.utcnow().isoformat()

        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()

    except Exception as e:
        logger.exception(f"Job {job_id} failed with error: {e}")
        result.status = "failed"
        result.error = str(e)
        result.completed_at = datetime.utcnow().isoformat()

    # Store final result
    await redis.set(f"job:{job_id}", result.model_dump_json(), ex=86400)
    logger.info(f"Job {job_id} completed with status: {result.status}")

    return result.model_dump()


async def startup(ctx: dict[str, Any]) -> None:
    """Worker startup hook - initialize services.

    Called once when worker starts. Initializes shared services
    to avoid re-creating them for each job.
    """
    logger.info("Initializing worker services...")
    settings = get_settings()
    ctx["settings"] = settings
    ctx["ocr_service"] = OCRService(settings)
    ctx["extraction_service"] = create_extraction_service(settings)
    ctx["storage_service"] = StorageService(settings)
    logger.info("Worker services initialized")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Worker shutdown hook - cleanup resources."""
    logger.info("Worker shutting down...")


class WorkerSettings:
    """arq worker settings.

    Defines the worker configuration including:
    - Task functions to register
    - Redis connection settings
    - Job timeout and retry settings
    """

    functions = [process_document]
    on_startup = startup
    on_shutdown = shutdown

    # These will be set from environment
    redis_settings = None
    max_jobs = 10
    job_timeout = 300

    @classmethod
    def get_redis_settings(cls) -> Any:
        """Get Redis settings from configuration."""
        from arq.connections import RedisSettings as ArqRedisSettings

        settings = get_settings()
        # Parse redis URL
        url = settings.redis_url
        if url.startswith("redis://"):
            url = url[8:]
        host_port = url.split("/")[0]
        host, port = host_port.split(":") if ":" in host_port else (host_port, "6379")
        db = int(url.split("/")[1]) if "/" in url else 0

        return ArqRedisSettings(host=host, port=int(port), database=db)
