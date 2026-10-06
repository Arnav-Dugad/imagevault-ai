from types import SimpleNamespace
from datetime import UTC, datetime
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import UserDelegationKey

from app.core.config import Settings

import app.services.storage as storage_module


def test_public_client_uses_configured_region(monkeypatch):
    clients = []

    class FakeMinio:
        def __init__(self, endpoint, **kwargs):
            self.endpoint = endpoint
            self.options = kwargs
            clients.append(self)

    settings = SimpleNamespace(
        minio_bucket="imagevault",
        minio_endpoint="minio:9000",
        minio_public_endpoint="localhost:9000",
        minio_access_key="imagevault",
        minio_secret_key="test-secret",
        minio_secure=False,
        minio_public_secure=False,
        minio_region="us-east-1",
        presigned_url_expire_minutes=30,
    )
    monkeypatch.setattr(storage_module, "get_settings", lambda: settings)
    monkeypatch.setattr(storage_module, "Minio", FakeMinio)

    storage_module.ObjectStorage()

    assert len(clients) == 2
    assert clients[1].endpoint == "localhost:9000"
    assert clients[1].options["region"] == "us-east-1"


@pytest.fixture
def azure_storage(monkeypatch):
    client = MagicMock()
    client.account_name = "testvault"
    container = client.get_container_client.return_value
    container.get_blob_client.side_effect = lambda name: SimpleNamespace(
        url=f"https://testvault.blob.core.windows.net/imagevault/{name}"
    )
    delegation = UserDelegationKey()
    delegation.signed_oid = "00000000-0000-0000-0000-000000000001"
    delegation.signed_tid = "00000000-0000-0000-0000-000000000002"
    delegation.signed_start = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    delegation.signed_expiry = "2099-01-01T00:00:00Z"
    delegation.signed_service = "b"
    delegation.signed_version = "2023-11-03"
    delegation.value = "dGVzdC1kZWxlZ2F0aW9uLWtleQ=="
    client.get_user_delegation_key.return_value = delegation
    credential = object()
    monkeypatch.setattr(storage_module, "DefaultAzureCredential", lambda: credential)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(storage_module, "BlobServiceClient", factory)
    result = storage_module.create_storage(Settings(
        _env_file=None, storage_backend="azure",
        azure_storage_account_url="https://testvault.blob.core.windows.net",
    ))
    assert factory.call_args.kwargs["credential"] is credential
    return result, client, container


def test_azure_private_container_and_crud(azure_storage):
    storage, _, container = azure_storage
    storage.ensure_bucket()
    container.create_container.assert_called_once_with()
    container.create_container.side_effect = ResourceExistsError()
    storage.ensure_bucket()  # Existing private container is a supported startup.
    storage.put_bytes("users/one/original.png", b"photo", "image/png")
    call = container.upload_blob.call_args.kwargs
    assert call["content_settings"].content_type == "image/png"
    assert call["data"] == b"photo"
    container.download_blob.return_value.readall.return_value = b"photo"
    assert storage.get_bytes("users/one/original.png") == b"photo"
    container.exists.return_value = True
    assert storage.healthy()
    storage.delete(None)
    container.delete_blob.assert_not_called()
    storage.delete("users/one/original.png")
    container.delete_blob.assert_called_once_with("users/one/original.png", delete_snapshots="include")
    container.delete_blob.side_effect = ResourceNotFoundError()
    storage.delete("already-deleted.png")


def test_azure_sas_is_read_only_https_and_cached(azure_storage):
    storage, client, _ = azure_storage
    assert storage.presigned_get(None) is None
    client.get_user_delegation_key.assert_not_called()
    first = storage.presigned_get("users/one/original.png")
    second = storage.presigned_get("users/one/thumbnail.webp")
    assert first != second
    query = parse_qs(urlparse(first).query)
    assert query["sp"] == ["r"]
    assert query["spr"] == ["https"]
    assert query["sr"] == ["b"]
    assert "sig" in query
    expires = datetime.fromisoformat(query["se"][0].replace("Z", "+00:00"))
    assert 29 * 60 < (expires - datetime.now(UTC)).total_seconds() <= 30 * 60
    client.get_user_delegation_key.assert_called_once()
    storage._key_expiry = datetime.min.replace(tzinfo=UTC)
    storage.presigned_get("users/one/original.png")
    assert client.get_user_delegation_key.call_count == 2


def test_azure_permission_errors_are_not_hidden(azure_storage):
    storage, _, container = azure_storage
    container.create_container.side_effect = PermissionError("RBAC denied")
    with pytest.raises(PermissionError):
        storage.ensure_bucket()
    container.delete_blob.side_effect = PermissionError("RBAC denied")
    with pytest.raises(PermissionError):
        storage.delete("original.png")


@pytest.mark.parametrize("endpoint", ["", "http://example.com", "https://example.com/container", "https://example.com?sig=secret", "https://user:pass@example.com", "https://example.com\n"])
def test_azure_rejects_invalid_account_endpoints(endpoint):
    with pytest.raises(ValueError):
        storage_module.AzureBlobStorage(Settings(_env_file=None, azure_storage_account_url=endpoint))
