"""Where original photos are stored: a local folder or Azure Blob Storage.

Files are named by their SHA-256 fingerprint, so two identical photos share
one stored file. That is why exact duplicates use no extra space.
"""

from functools import lru_cache
from pathlib import Path

from app.config import azure_settings, data_dir


class LocalStorage:
    name = "local"

    def __init__(self, folder: Path):
        self.folder = folder

    def _path(self, key: str) -> Path:
        return self.folder / key[:2] / key

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class AzureBlobStorage:
    name = "azure"

    def __init__(self, connection_string: str, container: str):
        from azure.storage.blob import BlobServiceClient

        service = BlobServiceClient.from_connection_string(connection_string)
        self.account = service.account_name
        self.container = service.get_container_client(container)

    def check(self) -> None:
        """Create the container if needed. Raises if the connection string is wrong."""
        if not self.container.exists():
            self.container.create_container()

    def save(self, key: str, data: bytes, content_type: str) -> None:
        from azure.storage.blob import ContentSettings

        self.container.upload_blob(
            key, data, overwrite=True, content_settings=ContentSettings(content_type=content_type)
        )

    def read(self, key: str) -> bytes:
        return self.container.download_blob(key).readall()

    def delete(self, key: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self.container.delete_blob(key)
        except ResourceNotFoundError:
            pass


@lru_cache(maxsize=4)
def _azure(connection_string: str, container: str) -> AzureBlobStorage:
    return AzureBlobStorage(connection_string, container)


def azure_storage() -> AzureBlobStorage | None:
    connection_string, container, _ = azure_settings()
    return _azure(connection_string, container) if connection_string else None


def get_storage(name: str):
    """Return the storage a photo lives in ('local' or 'azure')."""
    if name == "azure":
        storage = azure_storage()
        if storage is None:
            raise RuntimeError("This photo is stored in Azure, but Azure is not connected.")
        return storage
    return LocalStorage(data_dir() / "photos")


def active_storage():
    """New uploads go to Azure when it is connected, otherwise to the local folder."""
    return azure_storage() or LocalStorage(data_dir() / "photos")
