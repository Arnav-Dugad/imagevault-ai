from datetime import timedelta
from io import BytesIO

from minio import Minio

from app.core.config import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.public_client = Minio(
            settings.minio_public_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_public_secure,
            # MinIO defaults to us-east-1. Supplying the configured region keeps URL
            # signing local instead of querying the browser-facing endpoint, which is
            # intentionally unreachable from inside the backend container.
            region=settings.minio_region,
        )
        self.expiry = timedelta(minutes=settings.presigned_url_expire_minutes)

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def healthy(self) -> bool:
        return self.client.bucket_exists(self.bucket)

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str | None) -> None:
        if key:
            self.client.remove_object(self.bucket, key)

    def presigned_get(self, key: str | None) -> str | None:
        if not key:
            return None
        return self.public_client.presigned_get_object(self.bucket, key, expires=self.expiry)


def create_storage():
    provider = get_settings().storage_provider
    if provider == "azure":
        from app.services.cloud_storage import AzureBlobStorage
        return AzureBlobStorage()
    if provider == "s3":
        from app.services.cloud_storage import S3Storage
        return S3Storage()
    return ObjectStorage()


storage = create_storage()
