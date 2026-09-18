"""Cloud adapters preserve object keys and the existing storage interface.

Cloud resources are provisioned explicitly, never during application startup.
"""
from datetime import datetime, timedelta, timezone
from threading import Lock

import boto3
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, ContentSettings, generate_blob_sas
from botocore.config import Config

from app.core.config import get_settings


class AzureBlobStorage:
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.azure_storage_container
        self.expiry = timedelta(minutes=settings.presigned_url_expire_minutes)
        options = {"connection_timeout": 5, "read_timeout": 30, "retry_total": 2}
        self.account_key = None
        if settings.azure_storage_connection_string:
            self.client = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string, **options
            )
            parts = dict(part.split("=", 1) for part in settings.azure_storage_connection_string.split(";") if "=" in part)
            self.account_key = parts.get("AccountKey")
            if not self.account_key:
                raise ValueError("Azure connection string must contain AccountKey to sign previews")
            if not self.client.url.startswith("https://"):
                raise ValueError("Azure storage must use HTTPS")
        else:
            self.client = BlobServiceClient(
                settings.azure_storage_account_url, credential=DefaultAzureCredential(), **options
            )
        self.container = self.client.get_container_client(self.bucket)
        self._delegation_key = None
        self._delegation_expiry = datetime.min.replace(tzinfo=timezone.utc)
        self._key_lock = Lock()

    def ensure_bucket(self):
        # A missing container is a setup error; do not grant runtime provisioning rights.
        self.container.get_container_properties()

    def healthy(self):
        self.ensure_bucket()
        return True

    def put_bytes(self, key, data, content_type):
        self.container.upload_blob(
            name=key, data=data, overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    def get_bytes(self, key):
        return self.container.download_blob(key).readall()

    def delete(self, key):
        if key:
            try:
                self.container.delete_blob(key, delete_snapshots="include")
            except ResourceNotFoundError:
                pass

    def presigned_get(self, key):
        if not key:
            return None
        now = datetime.now(timezone.utc)
        expiry = now + self.expiry
        signing = {"account_key": self.account_key}
        if not self.account_key:
            with self._key_lock:
                if self._delegation_key is None or self._delegation_expiry < expiry + timedelta(minutes=5):
                    end = now + timedelta(hours=2)
                    self._delegation_key = self.client.get_user_delegation_key(now - timedelta(minutes=5), end)
                    self._delegation_expiry = end
                signing = {"user_delegation_key": self._delegation_key}
        sas = generate_blob_sas(
            account_name=self.client.account_name, container_name=self.bucket, blob_name=key,
            permission=BlobSasPermissions(read=True), start=now - timedelta(minutes=5),
            expiry=expiry, protocol="https", **signing,
        )
        return f"{self.container.get_blob_client(key).url}?{sas}"


class S3Storage:
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.expiry = settings.presigned_url_expire_minutes * 60
        # Standard credential chain supports EC2 roles and temporary session credentials.
        self.client = boto3.client(
            "s3", region_name=settings.s3_region,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30,
                          retries={"max_attempts": 3, "mode": "standard"}),
        )

    def ensure_bucket(self):
        self.client.head_bucket(Bucket=self.bucket)

    def healthy(self):
        self.ensure_bucket()
        return True

    def put_bytes(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get_bytes(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            return response["Body"].read()
        finally:
            response["Body"].close()

    def delete(self, key):
        if key:
            self.client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_get(self, key):
        if not key:
            return None
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.expiry,
        )
