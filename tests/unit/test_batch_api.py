"""Unit tests for batch processing API endpoints.

Tests batch upload and status endpoints.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_arq_pool() -> AsyncMock:
    """Create mock arq pool."""
    mock = AsyncMock()
    mock.pool = AsyncMock()
    mock.pool.set = AsyncMock()
    mock.pool.get = AsyncMock()
    mock.enqueue_job = AsyncMock()
    return mock


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Create minimal valid image bytes (1x1 PNG)."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


class TestBatchUploadEndpoint:
    """Test batch upload endpoint."""

    def test_batch_upload_requires_queue_enabled(self, client: TestClient) -> None:
        """Should return 503 when queue is disabled."""
        with patch("services.api.main.settings") as mock_settings:
            mock_settings.queue_enabled = False

            response = client.post(
                "/api/v1/documents/upload/batch",
                files=[("files", ("test.png", b"fake", "image/png"))],
            )

            assert response.status_code == 503
            assert "not enabled" in response.json()["detail"]

    def test_batch_upload_empty_files(self, client: TestClient, mock_arq_pool: AsyncMock) -> None:
        """Should return 400 when no files provided."""
        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            response = client.post(
                "/api/v1/documents/upload/batch",
                files=[],
            )

            assert response.status_code == 422  # Validation error for required field

    def test_batch_upload_success(
        self,
        client: TestClient,
        mock_arq_pool: AsyncMock,
        sample_image_bytes: bytes,
    ) -> None:
        """Should queue multiple documents successfully."""
        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            files = [
                ("files", ("invoice1.png", sample_image_bytes, "image/png")),
                ("files", ("invoice2.png", sample_image_bytes, "image/png")),
                ("files", ("invoice3.png", sample_image_bytes, "image/png")),
            ]

            response = client.post(
                "/api/v1/documents/upload/batch",
                files=files,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] == 3
            assert data["status"] == "pending"
            assert len(data["documents"]) == 3
            assert "batch_id" in data

            # Verify jobs were enqueued
            assert mock_arq_pool.enqueue_job.call_count == 3

    def test_batch_upload_skips_invalid_files(
        self,
        client: TestClient,
        mock_arq_pool: AsyncMock,
        sample_image_bytes: bytes,
    ) -> None:
        """Should skip non-image files in batch."""
        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            files = [
                ("files", ("invoice1.png", sample_image_bytes, "image/png")),
                ("files", ("document.pdf", b"fake pdf", "application/pdf")),  # Invalid
                ("files", ("invoice2.png", sample_image_bytes, "image/png")),
            ]

            response = client.post(
                "/api/v1/documents/upload/batch",
                files=files,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] == 2  # Only valid images
            assert mock_arq_pool.enqueue_job.call_count == 2

    def test_batch_upload_with_extraction(
        self,
        client: TestClient,
        mock_arq_pool: AsyncMock,
        sample_image_bytes: bytes,
    ) -> None:
        """Should pass extract_fields to all jobs."""
        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            files = [
                ("files", ("invoice1.png", sample_image_bytes, "image/png")),
            ]

            response = client.post(
                "/api/v1/documents/upload/batch?extract_fields=true",
                files=files,
            )

            assert response.status_code == 200

            # Check that extract_fields=True was passed
            call_kwargs = mock_arq_pool.enqueue_job.call_args[1]
            assert call_kwargs["extract_fields"] is True


class TestBatchStatusEndpoint:
    """Test batch status endpoint."""

    def test_batch_status_requires_queue_enabled(self, client: TestClient) -> None:
        """Should return 503 when queue is disabled."""
        with patch("services.api.main.settings") as mock_settings:
            mock_settings.queue_enabled = False

            response = client.get("/api/v1/batches/batch-123")

            assert response.status_code == 503

    def test_batch_status_not_found(self, client: TestClient, mock_arq_pool: AsyncMock) -> None:
        """Should return 404 when batch not found."""
        mock_arq_pool.pool.get = AsyncMock(return_value=None)

        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            response = client.get("/api/v1/batches/nonexistent-batch")

            assert response.status_code == 404

    def test_batch_status_pending(self, client: TestClient, mock_arq_pool: AsyncMock) -> None:
        """Should return pending status when jobs are pending."""
        batch_data = {
            "batch_id": "batch-123",
            "job_ids": ["job-1", "job-2"],
            "total_documents": 2,
            "created_at": "2024-01-01T00:00:00",
        }

        job_data_1 = {
            "job_id": "job-1",
            "status": "pending",
            "document_id": "doc-1",
            "created_at": "2024-01-01T00:00:00",
        }

        job_data_2 = {
            "job_id": "job-2",
            "status": "pending",
            "document_id": "doc-2",
            "created_at": "2024-01-01T00:00:00",
        }

        async def mock_get(key: str) -> str | None:
            if key == "batch:batch-123":
                return json.dumps(batch_data)
            elif key == "job:job-1":
                return json.dumps(job_data_1)
            elif key == "job:job-2":
                return json.dumps(job_data_2)
            return None

        mock_arq_pool.pool.get = mock_get

        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            response = client.get("/api/v1/batches/batch-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            assert data["pending"] == 2
            assert data["completed"] == 0

    def test_batch_status_completed(self, client: TestClient, mock_arq_pool: AsyncMock) -> None:
        """Should return completed status when all jobs done."""
        batch_data = {
            "batch_id": "batch-123",
            "job_ids": ["job-1", "job-2"],
            "total_documents": 2,
            "created_at": "2024-01-01T00:00:00",
        }

        job_data = {
            "job_id": "job-1",
            "status": "completed",
            "document_id": "doc-1",
            "ocr_text": "Invoice text",
            "created_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:01:00",
        }

        async def mock_get(key: str) -> str | None:
            if key == "batch:batch-123":
                return json.dumps(batch_data)
            elif key.startswith("job:"):
                return json.dumps(job_data)
            return None

        mock_arq_pool.pool.get = mock_get

        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            response = client.get("/api/v1/batches/batch-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["completed"] == 2

    def test_batch_status_partial(self, client: TestClient, mock_arq_pool: AsyncMock) -> None:
        """Should return partial status when some jobs failed."""
        batch_data = {
            "batch_id": "batch-123",
            "job_ids": ["job-1", "job-2"],
            "total_documents": 2,
            "created_at": "2024-01-01T00:00:00",
        }

        async def mock_get(key: str) -> str | None:
            if key == "batch:batch-123":
                return json.dumps(batch_data)
            elif key == "job:job-1":
                return json.dumps(
                    {
                        "job_id": "job-1",
                        "status": "completed",
                        "document_id": "doc-1",
                    }
                )
            elif key == "job:job-2":
                return json.dumps(
                    {
                        "job_id": "job-2",
                        "status": "failed",
                        "document_id": "doc-2",
                        "error": "OCR failed",
                    }
                )
            return None

        mock_arq_pool.pool.get = mock_get

        with (
            patch("services.api.main.settings") as mock_settings,
            patch("services.api.main.get_arq_pool", return_value=mock_arq_pool),
        ):
            mock_settings.queue_enabled = True

            response = client.get("/api/v1/batches/batch-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "partial"
            assert data["completed"] == 1
            assert data["failed"] == 1
