from datetime import UTC, datetime, timedelta
from io import BytesIO
from threading import Lock
from typing import Protocol
from urllib.parse import urlparse

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, ContentSettings, generate_blob_sas
from minio import Minio

from app.core.config import Settings, get_settings


class Storage(Protocol):
    bucket: str

    def ensure_bucket(self) -> None: ...
    def healthy(self) -> bool: ...
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def delete(self, key: str | None) -> None: ...
    def presigned_get(self, key: str | None) -> str | None: ...


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


class AzureBlobStorage:
    """Private Blob Storage using Entra credentials and read-only delegation SAS.

    On Azure the VM's managed identity supplies credentials; no account key is
    stored in the app. Delegation keys are cached per process to avoid one Azure
    round trip for every gallery thumbnail.
    """

    def __init__(self, settings: Settings) -> None:
        endpoint = settings.azure_storage_account_url.rstrip("/")
        parsed = urlparse(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or parsed.username or parsed.port or any(c.isspace() for c in endpoint)):
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL must be an HTTPS account endpoint")
        self.bucket = settings.azure_storage_container
        self.client = BlobServiceClient(
            account_url=endpoint,
            credential=DefaultAzureCredential(),
            connection_timeout=5,
            read_timeout=30,
            retry_total=2,
        )
        self.container = self.client.get_container_client(self.bucket)
        self.expiry = timedelta(minutes=settings.presigned_url_expire_minutes)
        self._delegation_key = None
        self._key_expiry = datetime.min.replace(tzinfo=UTC)
        self._key_lock = Lock()

    def ensure_bucket(self) -> None:
        try:
            self.container.create_container()  # Private by default.
        except ResourceExistsError:
            pass

    def healthy(self) -> bool:
        return self.container.exists()

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.container.upload_blob(
            name=key, data=data, overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    def get_bytes(self, key: str) -> bytes:
        return self.container.download_blob(key).readall()

    def delete(self, key: str | None) -> None:
        if key:
            try:
                self.container.delete_blob(key, delete_snapshots="include")
            except ResourceNotFoundError:
                pass  # Same idempotent behavior as the S3 delete operation.

    def presigned_get(self, key: str | None) -> str | None:
        if not key:
            return None
        now = datetime.now(UTC)
        expires = now + self.expiry
        with self._key_lock:
            if self._delegation_key is None or self._key_expiry < expires + timedelta(minutes=5):
                self._key_expiry = expires + timedelta(hours=1)
                self._delegation_key = self.client.get_user_delegation_key(
                    key_start_time=now - timedelta(minutes=5), key_expiry_time=self._key_expiry,
                )
            delegation_key = self._delegation_key
        sas = generate_blob_sas(
            account_name=self.client.account_name,
            container_name=self.bucket,
            blob_name=key,
            user_delegation_key=delegation_key,
            permission=BlobSasPermissions(read=True),
            start=now - timedelta(minutes=5),
            expiry=expires,
            protocol="https",
        )
        return f"{self.container.get_blob_client(key).url}?{sas}"


def create_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "azure":
        return AzureBlobStorage(settings)
    return ObjectStorage()


storage = create_storage(get_settings())
