from types import SimpleNamespace

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
