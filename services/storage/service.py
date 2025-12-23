"""S3-compatible object storage service using MinIO.

Production-grade implementation with:
- Connection pooling and retry logic
- Bucket auto-creation
- Presigned URL generation for secure downloads
- Content-type detection
- Comprehensive error handling

Based on MinIO Python SDK:
https://min.io/docs/minio/linux/developers/python/API.html
"""

import io
import logging
import mimetypes
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from services.shared.config import Settings

logger = logging.getLogger(__name__)


class StorageResult(BaseModel):
    """Result of storage operation.

    Attributes:
        success: Whether operation succeeded
        object_name: Full object path in storage
        bucket: Bucket name
        error: Error message if operation failed
        etag: Object ETag (hash) if available
        size: Object size in bytes if available
    """

    success: bool
    object_name: str | None = None
    bucket: str | None = None
    error: str | None = None
    etag: str | None = None
    size: int | None = None


class PresignedUrlResult(BaseModel):
    """Result of presigned URL generation.

    Attributes:
        success: Whether operation succeeded
        url: Presigned URL for object access
        expires_in_seconds: URL expiration time
        error: Error message if operation failed
    """

    success: bool
    url: str | None = None
    expires_in_seconds: int | None = None
    error: str | None = None


class StorageService:
    """S3-compatible object storage service.

    Provides document storage with data sovereignty support
    through on-premises MinIO deployment.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize storage service.

        Args:
            settings: Application settings with storage configuration
        """
        self.settings = settings
        self._client: Minio | None = None
        self._bucket_exists_cache: set[str] = set()

    def _get_client(self) -> Minio:
        """Get or create MinIO client (lazy initialization).

        Returns:
            Configured Minio client instance

        Raises:
            ValueError: If storage credentials are not configured
        """
        if self._client is None:
            if not self.settings.storage_access_key:
                raise ValueError(
                    "Storage access key not configured. "
                    "Set APP_STORAGE_ACCESS_KEY environment variable."
                )
            if not self.settings.storage_secret_key:
                raise ValueError(
                    "Storage secret key not configured. "
                    "Set APP_STORAGE_SECRET_KEY environment variable."
                )

            self._client = Minio(
                endpoint=self.settings.storage_endpoint,
                access_key=self.settings.storage_access_key,
                secret_key=self.settings.storage_secret_key,
                secure=self.settings.storage_secure,
            )
            logger.info(f"MinIO client initialized for endpoint: {self.settings.storage_endpoint}")

        return self._client

    def is_available(self) -> bool:
        """Check if storage service is available and configured.

        Returns:
            True if storage is enabled and credentials are set
        """
        if not self.settings.storage_enabled:
            return False

        return bool(self.settings.storage_access_key and self.settings.storage_secret_key)

    def health_check(self) -> bool:
        """Check if storage backend is reachable.

        Returns:
            True if MinIO server responds to list_buckets
        """
        if not self.is_available():
            return False

        try:
            client = self._get_client()
            client.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"Storage health check failed: {e}")
            return False

    def _ensure_bucket(self, bucket: str) -> None:
        """Ensure bucket exists, create if missing.

        Args:
            bucket: Bucket name to check/create
        """
        if bucket in self._bucket_exists_cache:
            return

        client = self._get_client()
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info(f"Created bucket: {bucket}")

        self._bucket_exists_cache.add(bucket)

    @staticmethod
    def _detect_content_type(filename: str) -> str:
        """Detect content type from filename.

        Args:
            filename: File name with extension

        Returns:
            MIME type string
        """
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def upload_file(
        self,
        file_path: Path,
        object_name: str,
        bucket: str | None = None,
    ) -> StorageResult:
        """Upload file to storage.

        Args:
            file_path: Local file path to upload
            object_name: Target object name in storage
            bucket: Target bucket (defaults to settings.storage_bucket)

        Returns:
            StorageResult with upload details
        """
        bucket = bucket or self.settings.storage_bucket

        try:
            if not file_path.exists():
                return StorageResult(
                    success=False,
                    error=f"File not found: {file_path}",
                )

            client = self._get_client()
            self._ensure_bucket(bucket)

            content_type = self._detect_content_type(file_path.name)
            file_size = file_path.stat().st_size

            result = client.fput_object(
                bucket_name=bucket,
                object_name=object_name,
                file_path=str(file_path),
                content_type=content_type,
            )

            logger.info(f"Uploaded {object_name} to {bucket} ({file_size} bytes)")

            return StorageResult(
                success=True,
                object_name=object_name,
                bucket=bucket,
                etag=result.etag,
                size=file_size,
            )

        except S3Error as e:
            logger.error(f"S3 error uploading {object_name}: {e}")
            return StorageResult(
                success=False,
                object_name=object_name,
                bucket=bucket,
                error=f"S3 error: {e.code} - {e.message}",
            )
        except Exception as e:
            logger.error(f"Error uploading {object_name}: {e}")
            return StorageResult(
                success=False,
                object_name=object_name,
                bucket=bucket,
                error=str(e),
            )

    @retry(
        retry=retry_if_exception_type(S3Error),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str | None = None,
        bucket: str | None = None,
    ) -> StorageResult:
        """Upload bytes to storage.

        Args:
            data: Bytes to upload
            object_name: Target object name in storage
            content_type: MIME type (auto-detected if not provided)
            bucket: Target bucket (defaults to settings.storage_bucket)

        Returns:
            StorageResult with upload details
        """
        bucket = bucket or self.settings.storage_bucket

        try:
            client = self._get_client()
            self._ensure_bucket(bucket)

            if content_type is None:
                content_type = self._detect_content_type(object_name)

            data_stream: BinaryIO = io.BytesIO(data)
            data_length = len(data)

            result = client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=data_stream,
                length=data_length,
                content_type=content_type,
            )

            logger.info(f"Uploaded {object_name} to {bucket} ({data_length} bytes)")

            return StorageResult(
                success=True,
                object_name=object_name,
                bucket=bucket,
                etag=result.etag,
                size=data_length,
            )

        except S3Error as e:
            logger.error(f"S3 error uploading {object_name}: {e}")
            return StorageResult(
                success=False,
                object_name=object_name,
                bucket=bucket,
                error=f"S3 error: {e.code} - {e.message}",
            )
        except Exception as e:
            logger.error(f"Error uploading {object_name}: {e}")
            return StorageResult(
                success=False,
                object_name=object_name,
                bucket=bucket,
                error=str(e),
            )

    def get_presigned_url(
        self,
        object_name: str,
        bucket: str | None = None,
        expires_seconds: int = 3600,
    ) -> PresignedUrlResult:
        """Generate presigned URL for secure object download.

        Args:
            object_name: Object name in storage
            bucket: Bucket name (defaults to settings.storage_bucket)
            expires_seconds: URL expiration time in seconds (default: 1 hour)

        Returns:
            PresignedUrlResult with URL or error
        """
        bucket = bucket or self.settings.storage_bucket

        try:
            client = self._get_client()

            url = client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
            )

            return PresignedUrlResult(
                success=True,
                url=url,
                expires_in_seconds=expires_seconds,
            )

        except S3Error as e:
            logger.error(f"S3 error generating presigned URL for {object_name}: {e}")
            return PresignedUrlResult(
                success=False,
                error=f"S3 error: {e.code} - {e.message}",
            )
        except Exception as e:
            logger.error(f"Error generating presigned URL for {object_name}: {e}")
            return PresignedUrlResult(
                success=False,
                error=str(e),
            )

    def delete_object(
        self,
        object_name: str,
        bucket: str | None = None,
    ) -> StorageResult:
        """Delete object from storage.

        Args:
            object_name: Object name to delete
            bucket: Bucket name (defaults to settings.storage_bucket)

        Returns:
            StorageResult indicating success or failure
        """
        bucket = bucket or self.settings.storage_bucket

        try:
            client = self._get_client()
            client.remove_object(bucket_name=bucket, object_name=object_name)

            logger.info(f"Deleted {object_name} from {bucket}")

            return StorageResult(
                success=True,
                object_name=object_name,
                bucket=bucket,
            )

        except S3Error as e:
            logger.error(f"S3 error deleting {object_name}: {e}")
            return StorageResult(
                success=False,
                object_name=object_name,
                bucket=bucket,
                error=f"S3 error: {e.code} - {e.message}",
            )
        except Exception as e:
            logger.error(f"Error deleting {object_name}: {e}")
            return StorageResult(
                success=False,
                object_name=object_name,
                bucket=bucket,
                error=str(e),
            )

    def object_exists(
        self,
        object_name: str,
        bucket: str | None = None,
    ) -> bool:
        """Check if object exists in storage.

        Args:
            object_name: Object name to check
            bucket: Bucket name (defaults to settings.storage_bucket)

        Returns:
            True if object exists
        """
        bucket = bucket or self.settings.storage_bucket

        try:
            client = self._get_client()
            client.stat_object(bucket_name=bucket, object_name=object_name)
            return True
        except S3Error:
            return False
        except Exception:
            return False
