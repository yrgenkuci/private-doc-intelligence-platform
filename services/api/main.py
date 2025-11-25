"""FastAPI application for document ingestion.

Production-ready API with:
- Health and readiness checks for Kubernetes
- File upload validation
- Async OCR processing
- Structured error responses

Based on FastAPI best practices:
https://fastapi.tiangolo.com/
"""

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from services.ocr.service import OCRService
from services.shared.config import get_settings

settings = get_settings()
app = FastAPI(
    title="Document Intelligence Platform",
    description="Private document intelligence API for OCR and extraction",
    version=settings.service_version,
)

ocr_service = OCRService(settings)


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

    # Save to temp file for OCR processing
    doc_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Process with OCR
        result = ocr_service.extract_text(tmp_path)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OCR processing failed: {result.error}",
            )

        return UploadResponse(success=True, document_id=doc_id, text=result.text)

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
