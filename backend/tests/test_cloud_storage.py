from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from azure.core.exceptions import ResourceNotFoundError
from botocore.exceptions import ClientError
from pydantic import ValidationError

from app.core.config import Settings
from app.services import cloud_storage
from app.services import storage as storage_module


def settings(**kwargs):
    return Settings(_env_file=None, **kwargs)


@pytest.mark.parametrize('provider', ['azure', 's3'])
def test_cloud_config_requires_destination(provider):
    with pytest.raises(ValidationError):
        settings(storage_provider=provider)


def test_production_rejects_default_secret_and_long_preview():
    with pytest.raises(ValidationError):
        settings(environment='production')
    with pytest.raises(ValidationError):
        settings(presigned_url_expire_minutes=61)


def test_provider_selection(monkeypatch):
    for provider, name in [('azure', 'AzureBlobStorage'), ('s3', 'S3Storage')]:
        sentinel = object()
        monkeypatch.setattr(storage_module, 'get_settings', lambda: SimpleNamespace(storage_provider=provider))
        monkeypatch.setattr(cloud_storage, name, lambda: sentinel)
        assert storage_module.create_storage() is sentinel


def azure(monkeypatch):
    config = settings(storage_provider='azure', azure_storage_connection_string=(
        'DefaultEndpointsProtocol=https;AccountName=testvault;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net'
    ))
    monkeypatch.setattr(cloud_storage, 'get_settings', lambda: config)
    return cloud_storage.AzureBlobStorage()


def test_azure_signed_preview_is_read_only_https_and_escaped(monkeypatch):
    adapter = azure(monkeypatch)
    url = adapter.presigned_get('users/a photo.jpg')
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == 'https'
    assert parsed.path == '/imagevault/users/a%20photo.jpg'
    assert query['sp'] == ['r']
    assert query['spr'] == ['https']
    assert 'sig' in query
    assert adapter.presigned_get(None) is None


def test_azure_crud_and_missing_delete(monkeypatch):
    adapter = azure(monkeypatch)
    adapter.container = MagicMock()
    adapter.container.download_blob.return_value.readall.return_value = b'photo'
    adapter.put_bytes('key', b'photo', 'image/jpeg')
    assert adapter.container.upload_blob.call_args.kwargs['content_settings'].content_type == 'image/jpeg'
    assert adapter.get_bytes('key') == b'photo'
    assert adapter.healthy()
    adapter.container.create_container.assert_not_called()
    adapter.container.delete_blob.side_effect = ResourceNotFoundError('missing')
    adapter.delete('missing')
    adapter.container.delete_blob.side_effect = RuntimeError('permission denied')
    with pytest.raises(RuntimeError):
        adapter.delete('private')


def test_azure_managed_identity_caches_delegation_key(monkeypatch):
    monkeypatch.setattr(cloud_storage, 'get_settings', lambda: settings(
        storage_provider='azure', azure_storage_account_url='https://testvault.blob.core.windows.net'
    ))
    client = MagicMock(account_name='testvault')
    client.get_container_client.return_value.get_blob_client.return_value.url = 'https://testvault.blob.core.windows.net/imagevault/a'
    monkeypatch.setattr(cloud_storage, 'DefaultAzureCredential', MagicMock())
    monkeypatch.setattr(cloud_storage, 'BlobServiceClient', MagicMock(return_value=client))
    signer = MagicMock(return_value='signed')
    monkeypatch.setattr(cloud_storage, 'generate_blob_sas', signer)
    adapter = cloud_storage.AzureBlobStorage()
    adapter.presigned_get('a')
    adapter.presigned_get('b')
    client.get_user_delegation_key.assert_called_once()
    assert signer.call_args.kwargs['user_delegation_key'] == client.get_user_delegation_key.return_value
    assert signer.call_args.kwargs['protocol'] == 'https'


def test_s3_uses_region_role_chain_and_closes_download(monkeypatch):
    monkeypatch.setattr(cloud_storage, 'get_settings', lambda: settings(
        storage_provider='s3', s3_bucket='private-vault', s3_region='ap-south-1'
    ))
    client = MagicMock()
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(cloud_storage.boto3, 'client', factory)
    adapter = cloud_storage.S3Storage()
    assert factory.call_args.kwargs['region_name'] == 'ap-south-1'
    assert 'aws_access_key_id' not in factory.call_args.kwargs
    body = BytesIO(b'photo')
    client.get_object.return_value = {'Body': body}
    assert adapter.get_bytes('key') == b'photo'
    assert body.closed
    adapter.put_bytes('key', b'photo', 'image/jpeg')
    client.put_object.assert_called_once_with(Bucket='private-vault', Key='key', Body=b'photo', ContentType='image/jpeg')
    adapter.presigned_get('key')
    client.generate_presigned_url.assert_called_once_with('get_object', Params={'Bucket': 'private-vault', 'Key': 'key'}, ExpiresIn=1800)
    assert adapter.healthy()
    client.create_bucket.assert_not_called()
    client.head_bucket.side_effect = ClientError({'Error': {'Code': '403'}}, 'HeadBucket')
    with pytest.raises(ClientError):
        adapter.healthy()
    adapter.delete(None)
    client.delete_object.assert_not_called()
    adapter.delete('key')
    client.delete_object.assert_called_once_with(Bucket='private-vault', Key='key')
