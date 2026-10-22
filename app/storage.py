"""Where files are stored: Azure Blob Storage on Azure, or a local folder on your computer.

Files are named by the photo's SHA-256 fingerprint, so identical photos share one file:
  originals/<sha256>        the uploaded photo
  thumbnails/<sha256>.jpg   a small preview
"""

from functools import lru_cache
from pathlib import Path

from app.config import data_dir, env


class LocalStorage:
    kind = "local"

    def __init__(self, folder: Path):
        self.folder = folder
        self.description = f"Local folder ({folder})"

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self.folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return (self.folder / key).read_bytes()

    def delete(self, key: str) -> None:
        (self.folder / key).unlink(missing_ok=True)

    def check(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)


class AzureBlobStorage:
    kind = "azure"

    def __init__(self, container_name: str, account_url: str = "", connection_string: str = ""):
        from azure.storage.blob import BlobServiceClient

        if connection_string:
            service = BlobServiceClient.from_connection_string(connection_string)
        else:
            from azure.identity import DefaultAzureCredential  # the App Service's managed identity

            service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        self.container = service.get_container_client(container_name)
        self.description = f"{service.account_name} / {container_name}"

    def save(self, key: str, data: bytes, content_type: str) -> None:
        from azure.storage.blob import ContentSettings

        settings = ContentSettings(content_type=content_type)
        self.container.upload_blob(key, data, overwrite=True, content_settings=settings)

    def read(self, key: str) -> bytes:
        return self.container.download_blob(key).readall()

    def delete(self, key: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self.container.delete_blob(key)
        except ResourceNotFoundError:
            pass

    def check(self) -> None:
        """Create the container if needed; raises if Azure can't be reached."""
        if not self.container.exists():
            self.container.create_container()


@lru_cache(maxsize=4)
def _storage(account_url: str, connection_string: str, container: str, folder: str):
    storage = AzureBlobStorage(container, account_url, connection_string) if account_url or connection_string \
        else LocalStorage(Path(folder))
    storage.check()  # make sure the container/folder exists before first use
    return storage


def get_storage():
    return _storage(
        env("AZURE_STORAGE_ACCOUNT_URL"),
        env("AZURE_STORAGE_CONNECTION_STRING"),
        env("AZURE_STORAGE_CONTAINER", "photos"),
        str(data_dir() / "storage"),
    )


def original_key(sha256: str) -> str:
    return f"originals/{sha256}"


def thumbnail_key(sha256: str) -> str:
    return f"thumbnails/{sha256}.jpg"
