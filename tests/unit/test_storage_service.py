"""Unit tests for StorageService (MinIO/S3-compatible storage).

Tests storage operations with mocked MinIO client.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from services.shared.config import Settings
from services.storage.service import StorageService


@pytest.fixture
def storage_settings() -> Settings:
    """Create test settings with storage enabled."""
    return Settings(
        storage_enabled=True,
        storage_endpoint="localhost:9000",
        storage_access_key="test-access-key",
        storage_secret_key="test-secret-key",
        storage_bucket="test-documents",
        storage_secure=False,
    )


@pytest.fixture
def disabled_storage_settings() -> Settings:
    """Create test settings with storage disabled."""
    return Settings(storage_enabled=False)


@pytest.fixture
def mock_minio_client() -> MagicMock:
    """Create mock MinIO client."""
    mock = MagicMock()
    mock.bucket_exists.return_value = True
    mock.list_buckets.return_value = []
    return mock


class TestStorageServiceAvailability:
    """Test storage service availability checks."""

    def test_is_available_when_enabled_and_configured(self, storage_settings: Settings) -> None:
        """Should return True when storage is enabled and credentials are set."""
        service = StorageService(storage_settings)
        assert service.is_available() is True

    def test_is_not_available_when_disabled(self, disabled_storage_settings: Settings) -> None:
        """Should return False when storage is disabled."""
        service = StorageService(disabled_storage_settings)
        assert service.is_available() is False

    def test_is_not_available_without_access_key(self) -> None:
        """Should return False when access key is missing."""
        settings = Settings(
            storage_enabled=True,
            storage_access_key="",
            storage_secret_key="secret",
        )
        service = StorageService(settings)
        assert service.is_available() is False

    def test_is_not_available_without_secret_key(self) -> None:
        """Should return False when secret key is missing."""
        settings = Settings(
            storage_enabled=True,
            storage_access_key="access",
            storage_secret_key="",
        )
        service = StorageService(settings)
        assert service.is_available() is False


class TestStorageServiceHealthCheck:
    """Test storage service health checks."""

    def test_health_check_success(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should return True when MinIO is reachable."""
        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            assert service.health_check() is True

        mock_minio_client.list_buckets.assert_called_once()

    def test_health_check_failure(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should return False when MinIO is not reachable."""
        mock_minio_client.list_buckets.side_effect = Exception("Connection refused")
        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            assert service.health_check() is False

    def test_health_check_when_disabled(self, disabled_storage_settings: Settings) -> None:
        """Should return False when storage is disabled."""
        service = StorageService(disabled_storage_settings)
        assert service.health_check() is False


class TestStorageServiceUpload:
    """Test storage upload operations."""

    def test_upload_bytes_success(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should upload bytes successfully."""
        mock_minio_client.put_object.return_value = MagicMock(etag="abc123")

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.upload_bytes(
                data=b"test data",
                object_name="doc-123/invoice.pdf",
            )

        assert result.success is True
        assert result.object_name == "doc-123/invoice.pdf"
        assert result.bucket == "test-documents"
        assert result.etag == "abc123"
        assert result.size == 9

    def test_upload_bytes_creates_bucket_if_missing(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should create bucket if it doesn't exist."""
        mock_minio_client.bucket_exists.return_value = False
        mock_minio_client.put_object.return_value = MagicMock(etag="abc123")

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.upload_bytes(
                data=b"test data",
                object_name="doc-123/invoice.pdf",
            )

        assert result.success is True
        mock_minio_client.make_bucket.assert_called_once_with("test-documents")

    def test_upload_bytes_s3_error(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should handle S3 errors gracefully."""
        mock_minio_client.put_object.side_effect = S3Error(
            code="NoSuchBucket",
            message="Bucket does not exist",
            resource="/test-bucket",
            request_id="12345",
            host_id="host",
            response=MagicMock(status=404, data=b""),
        )

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.upload_bytes(
                data=b"test data",
                object_name="doc-123/invoice.pdf",
            )

        assert result.success is False
        assert "S3 error" in str(result.error)

    def test_upload_file_not_found(self, storage_settings: Settings) -> None:
        """Should handle missing file gracefully."""
        service = StorageService(storage_settings)
        result = service.upload_file(
            file_path=Path("/nonexistent/file.pdf"),
            object_name="doc-123/invoice.pdf",
        )

        assert result.success is False
        assert "not found" in str(result.error).lower()

    def test_upload_file_success(
        self,
        storage_settings: Settings,
        mock_minio_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should upload file successfully."""
        # Create test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")

        mock_minio_client.fput_object.return_value = MagicMock(etag="file123")

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.upload_file(
                file_path=test_file,
                object_name="doc-123/invoice.pdf",
            )

        assert result.success is True
        assert result.etag == "file123"
        assert result.size == 11  # len(b"PDF content")


class TestStorageServicePresignedUrl:
    """Test presigned URL generation."""

    def test_get_presigned_url_success(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should generate presigned URL successfully."""
        expected_url = "https://minio:9000/test-documents/doc-123/invoice.pdf?signature=abc"
        mock_minio_client.presigned_get_object.return_value = expected_url

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.get_presigned_url(
                object_name="doc-123/invoice.pdf",
                expires_seconds=7200,
            )

        assert result.success is True
        assert result.url == expected_url
        assert result.expires_in_seconds == 7200

    def test_get_presigned_url_s3_error(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should handle S3 errors gracefully."""
        mock_minio_client.presigned_get_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test-bucket/doc-123",
            request_id="12345",
            host_id="host",
            response=MagicMock(status=404, data=b""),
        )

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.get_presigned_url(object_name="doc-123/invoice.pdf")

        assert result.success is False
        assert "S3 error" in str(result.error)


class TestStorageServiceDelete:
    """Test storage delete operations."""

    def test_delete_object_success(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should delete object successfully."""
        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.delete_object(object_name="doc-123/invoice.pdf")

        assert result.success is True
        mock_minio_client.remove_object.assert_called_once()

    def test_delete_object_s3_error(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should handle S3 errors gracefully."""
        mock_minio_client.remove_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test-bucket/doc-123",
            request_id="12345",
            host_id="host",
            response=MagicMock(status=404, data=b""),
        )

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            result = service.delete_object(object_name="doc-123/invoice.pdf")

        assert result.success is False


class TestStorageServiceObjectExists:
    """Test object existence checks."""

    def test_object_exists_true(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should return True when object exists."""
        mock_minio_client.stat_object.return_value = MagicMock()

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            assert service.object_exists("doc-123/invoice.pdf") is True

    def test_object_exists_false(
        self, storage_settings: Settings, mock_minio_client: MagicMock
    ) -> None:
        """Should return False when object doesn't exist."""
        mock_minio_client.stat_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Object not found",
            resource="/test-bucket/doc-123",
            request_id="12345",
            host_id="host",
            response=MagicMock(status=404, data=b""),
        )

        service = StorageService(storage_settings)

        with patch.object(service, "_get_client", return_value=mock_minio_client):
            assert service.object_exists("doc-123/invoice.pdf") is False


class TestStorageServiceContentType:
    """Test content type detection."""

    def test_detect_pdf_content_type(self) -> None:
        """Should detect PDF content type."""
        assert StorageService._detect_content_type("invoice.pdf") == "application/pdf"

    def test_detect_image_content_type(self) -> None:
        """Should detect image content types."""
        assert StorageService._detect_content_type("photo.jpg") == "image/jpeg"
        assert StorageService._detect_content_type("photo.png") == "image/png"

    def test_detect_unknown_content_type(self) -> None:
        """Should return octet-stream for unknown types."""
        result = StorageService._detect_content_type("data.unknown_ext_12345")
        assert result == "application/octet-stream"


class TestStorageSettingsConfiguration:
    """Test storage settings via environment variables."""

    def test_default_storage_disabled(self) -> None:
        """Storage should be disabled by default when no env vars set."""
        import os

        # Clear any existing storage env vars to test true defaults
        env_backup = {}
        storage_vars = [
            "APP_STORAGE_ENABLED",
            "APP_STORAGE_ENDPOINT",
            "APP_STORAGE_ACCESS_KEY",
            "APP_STORAGE_SECRET_KEY",
        ]
        for var in storage_vars:
            if var in os.environ:
                env_backup[var] = os.environ.pop(var)

        try:
            # Create settings without .env file influence
            settings = Settings(_env_file=None)
            assert settings.storage_enabled is False
        finally:
            # Restore env vars
            os.environ.update(env_backup)

    def test_storage_settings_from_env(self) -> None:
        """Should read storage settings from environment."""
        import os

        os.environ["APP_STORAGE_ENABLED"] = "true"
        os.environ["APP_STORAGE_ENDPOINT"] = "minio.example.com:9000"
        os.environ["APP_STORAGE_BUCKET"] = "my-docs"

        try:
            settings = Settings(_env_file=None)
            assert settings.storage_enabled is True
            assert settings.storage_endpoint == "minio.example.com:9000"
            assert settings.storage_bucket == "my-docs"
        finally:
            del os.environ["APP_STORAGE_ENABLED"]
            del os.environ["APP_STORAGE_ENDPOINT"]
            del os.environ["APP_STORAGE_BUCKET"]
