"""Unit tests for async queue functionality.

Tests task definitions and queue configuration.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.queue.tasks import JobResult, WorkerSettings, process_document
from services.shared.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Create test settings with queue enabled."""
    return Settings(
        queue_enabled=True,
        redis_url="redis://localhost:6379/0",
        queue_max_jobs=5,
        queue_job_timeout=60,
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis connection."""
    mock = AsyncMock()
    mock.set = AsyncMock()
    mock.get = AsyncMock()
    return mock


@pytest.fixture
def mock_ocr_result() -> MagicMock:
    """Create mock OCR result."""
    result = MagicMock()
    result.success = True
    result.text = "Invoice #12345 Total: $100.00"
    return result


@pytest.fixture
def mock_extraction_result() -> MagicMock:
    """Create mock extraction result."""
    result = MagicMock()
    result.success = True
    result.invoice_data = MagicMock()
    result.invoice_data.model_dump_json.return_value = json.dumps(
        {"invoice_number": "12345", "total_amount": "100.00"}
    )
    return result


class TestJobResult:
    """Test JobResult model."""

    def test_job_result_pending(self) -> None:
        """Should create pending job result."""
        result = JobResult(
            job_id="job-123",
            status="pending",
            document_id="doc-456",
            created_at=datetime.utcnow().isoformat(),
        )
        assert result.status == "pending"
        assert result.ocr_text is None

    def test_job_result_completed(self) -> None:
        """Should create completed job result."""
        result = JobResult(
            job_id="job-123",
            status="completed",
            document_id="doc-456",
            ocr_text="Extracted text",
            extracted_data={"invoice_number": "12345"},
            storage_path="documents/doc-456/original.jpg",
            created_at=datetime.utcnow().isoformat(),
            completed_at=datetime.utcnow().isoformat(),
        )
        assert result.status == "completed"
        assert result.ocr_text == "Extracted text"

    def test_job_result_failed(self) -> None:
        """Should create failed job result."""
        result = JobResult(
            job_id="job-123",
            status="failed",
            document_id="doc-456",
            error="OCR failed: Invalid image",
            created_at=datetime.utcnow().isoformat(),
            completed_at=datetime.utcnow().isoformat(),
        )
        assert result.status == "failed"
        assert "OCR failed" in str(result.error)


class TestProcessDocumentTask:
    """Test process_document task."""

    @pytest.mark.asyncio
    async def test_process_document_success(
        self,
        settings: Settings,
        mock_redis: AsyncMock,
        mock_ocr_result: MagicMock,
    ) -> None:
        """Should process document successfully."""
        mock_ocr_service = MagicMock()
        mock_ocr_service.extract_text.return_value = mock_ocr_result

        mock_storage_service = MagicMock()
        mock_storage_service.is_available.return_value = False

        mock_extraction_service = MagicMock()

        ctx = {
            "redis": mock_redis,
            "settings": settings,
            "ocr_service": mock_ocr_service,
            "extraction_service": mock_extraction_service,
            "storage_service": mock_storage_service,
        }

        result = await process_document(
            ctx=ctx,
            job_id="job-123",
            document_id="doc-456",
            file_content=b"fake image data",
            filename="invoice.jpg",
            content_type="image/jpeg",
            extract_fields=False,
        )

        assert result["status"] == "completed"
        assert result["ocr_text"] == "Invoice #12345 Total: $100.00"
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_process_document_ocr_failure(
        self,
        settings: Settings,
        mock_redis: AsyncMock,
    ) -> None:
        """Should handle OCR failure gracefully."""
        mock_ocr_result = MagicMock()
        mock_ocr_result.success = False
        mock_ocr_result.error = "Invalid image format"

        mock_ocr_service = MagicMock()
        mock_ocr_service.extract_text.return_value = mock_ocr_result

        mock_storage_service = MagicMock()
        mock_storage_service.is_available.return_value = False

        ctx = {
            "redis": mock_redis,
            "settings": settings,
            "ocr_service": mock_ocr_service,
            "extraction_service": MagicMock(),
            "storage_service": mock_storage_service,
        }

        result = await process_document(
            ctx=ctx,
            job_id="job-123",
            document_id="doc-456",
            file_content=b"bad data",
            filename="bad.jpg",
            content_type="image/jpeg",
            extract_fields=False,
        )

        assert result["status"] == "failed"
        assert "OCR failed" in str(result["error"])

    @pytest.mark.asyncio
    async def test_process_document_with_extraction(
        self,
        settings: Settings,
        mock_redis: AsyncMock,
        mock_ocr_result: MagicMock,
        mock_extraction_result: MagicMock,
    ) -> None:
        """Should run extraction when requested."""
        mock_ocr_service = MagicMock()
        mock_ocr_service.extract_text.return_value = mock_ocr_result

        mock_extraction_service = MagicMock()
        mock_extraction_service.extract_invoice_fields.return_value = mock_extraction_result

        mock_storage_service = MagicMock()
        mock_storage_service.is_available.return_value = False

        ctx = {
            "redis": mock_redis,
            "settings": settings,
            "ocr_service": mock_ocr_service,
            "extraction_service": mock_extraction_service,
            "storage_service": mock_storage_service,
        }

        result = await process_document(
            ctx=ctx,
            job_id="job-123",
            document_id="doc-456",
            file_content=b"fake image data",
            filename="invoice.jpg",
            content_type="image/jpeg",
            extract_fields=True,
        )

        assert result["status"] == "completed"
        assert result["extracted_data"] is not None
        mock_extraction_service.extract_invoice_fields.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_with_storage(
        self,
        settings: Settings,
        mock_redis: AsyncMock,
        mock_ocr_result: MagicMock,
    ) -> None:
        """Should store document when storage is available."""
        mock_ocr_service = MagicMock()
        mock_ocr_service.extract_text.return_value = mock_ocr_result

        mock_storage_result = MagicMock()
        mock_storage_result.success = True
        mock_storage_result.bucket = "documents"

        mock_storage_service = MagicMock()
        mock_storage_service.is_available.return_value = True
        mock_storage_service.upload_bytes.return_value = mock_storage_result

        ctx = {
            "redis": mock_redis,
            "settings": settings,
            "ocr_service": mock_ocr_service,
            "extraction_service": MagicMock(),
            "storage_service": mock_storage_service,
        }

        result = await process_document(
            ctx=ctx,
            job_id="job-123",
            document_id="doc-456",
            file_content=b"fake image data",
            filename="invoice.jpg",
            content_type="image/jpeg",
            extract_fields=False,
        )

        assert result["status"] == "completed"
        assert result["storage_path"] == "documents/doc-456/original.jpg"
        mock_storage_service.upload_bytes.assert_called_once()


class TestWorkerSettings:
    """Test WorkerSettings configuration."""

    def test_worker_functions_registered(self) -> None:
        """Should have process_document task registered."""
        assert process_document in WorkerSettings.functions

    def test_get_redis_settings(self, settings: Settings) -> None:
        """Should parse Redis URL correctly."""
        with patch("services.queue.tasks.get_settings", return_value=settings):
            redis_settings = WorkerSettings.get_redis_settings()
            assert redis_settings.host == "localhost"
            assert redis_settings.port == 6379
            assert redis_settings.database == 0


class TestQueueSettings:
    """Test queue configuration via Settings."""

    def test_default_queue_disabled(self) -> None:
        """Queue should be disabled by default."""
        settings = Settings(_env_file=None)
        assert settings.queue_enabled is False

    def test_queue_settings_from_env(self) -> None:
        """Should read queue settings from environment."""
        import os

        os.environ["APP_QUEUE_ENABLED"] = "true"
        os.environ["APP_REDIS_URL"] = "redis://redis-server:6380/1"
        os.environ["APP_QUEUE_MAX_JOBS"] = "20"

        try:
            settings = Settings(_env_file=None)
            assert settings.queue_enabled is True
            assert settings.redis_url == "redis://redis-server:6380/1"
            assert settings.queue_max_jobs == 20
        finally:
            del os.environ["APP_QUEUE_ENABLED"]
            del os.environ["APP_REDIS_URL"]
            del os.environ["APP_QUEUE_MAX_JOBS"]
