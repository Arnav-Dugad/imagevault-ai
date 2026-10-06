"""Copy MinIO objects to Azure, preserving database object keys. Never delete source data."""
import argparse
import hashlib

from app.core.config import get_settings
from app.services.storage import AzureBlobStorage, ObjectStorage
from azure.storage.blob import ContentSettings


def migrate(apply: bool) -> None:
    settings = get_settings()
    source = ObjectStorage()
    target = AzureBlobStorage(settings)
    if apply:
        target.ensure_bucket()
    count, size = 0, 0
    for item in source.client.list_objects(source.bucket, recursive=True):
        count += 1
        size += item.size or 0
        if not apply:
            continue
        response = source.client.get_object(source.bucket, item.object_name)
        try:
            # Photos and videos may be large. Feed a stream to the SDK rather
            # than loading the entire original into migration-process memory.
            target.container.upload_blob(
                name=item.object_name,
                data=response,
                length=item.size,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type=response.headers.get('Content-Type', 'application/octet-stream')
                ),
                max_concurrency=1,
            )
        finally:
            response.close()
            response.release_conn()
        # Verify full content before reporting success. Multipart S3 ETags are
        # not content hashes and cannot be compared directly with Azure ETags.
        original = source.client.get_object(source.bucket, item.object_name)
        try:
            source_hash = hashlib.sha256()
            while chunk := original.read(1024 * 1024):
                source_hash.update(chunk)
        finally:
            original.close()
            original.release_conn()
        target_hash = hashlib.sha256()
        for chunk in target.container.download_blob(item.object_name).chunks():
            target_hash.update(chunk)
        if source_hash.digest() != target_hash.digest():
            raise RuntimeError(f'Content verification failed for {item.object_name}')
    print(f'{"Copied and verified" if apply else "Would copy"} {count} objects ({size} bytes). Source objects were retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Actually copy and verify objects; default is dry run')
    args = parser.parse_args()
    migrate(args.apply)
