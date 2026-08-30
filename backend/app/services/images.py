import hashlib
import math
import re
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

from app.core.config import get_settings
from app.models import DuplicateType, Image
from app.schemas import ImageSummary
from app.services.storage import storage

PillowImage.MAX_IMAGE_PIXELS = 50_000_000

MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def read_validated_image(upload: UploadFile) -> tuple[bytes, str, str]:
    settings = get_settings()
    mime_type = (upload.content_type or "").lower()
    if mime_type not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type: {mime_type or 'unknown'}",
        )

    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{upload.filename or 'Image'} exceeds the upload limit",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Empty files cannot be uploaded")

    try:
        with PillowImage.open(BytesIO(data)) as image:
            image.verify()
            detected = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, PillowImage.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="The file is not a valid image") from exc

    allowed_formats = {"JPEG", "PNG", "WEBP"}
    if detected not in allowed_formats:
        raise HTTPException(status_code=415, detail=f"Unsupported image format: {detected}")
    detected_mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[detected]
    if detected_mime != mime_type:
        raise HTTPException(status_code=400, detail="Declared image type does not match file content")

    safe_name = safe_filename(upload.filename or f"upload{MIME_EXTENSIONS[mime_type]}")
    return data, safe_name, mime_type


def safe_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[^\w.()\- ]+", "_", name, flags=re.UNICODE).strip(" .")
    return name[:255] or "image"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_keys(user_id: object, image_id: object, mime_type: str) -> tuple[str, str]:
    extension = MIME_EXTENSIONS[mime_type]
    root = f"users/{user_id}"
    return (
        f"{root}/originals/{image_id}{extension}",
        f"{root}/thumbnails/{image_id}.webp",
    )


def similarity_classification(score: float) -> str:
    if score >= 0.95:
        return "Very Similar"
    if score >= 0.85:
        return "Similar"
    if score >= 0.75:
        return "Possibly Related"
    return "Low Similarity"


def image_summary(image: Image, best_similarity: float | None = None) -> ImageSummary:
    return ImageSummary(
        id=image.id,
        original_filename=image.original_filename,
        mime_type=image.mime_type,
        file_size=image.file_size,
        width=image.width,
        height=image.height,
        sha256=image.sha256,
        perceptual_hash=image.perceptual_hash,
        status=image.status,
        exact_duplicate_of_id=image.exact_duplicate_of_id,
        created_at=image.created_at,
        processed_at=image.processed_at,
        thumbnail_url=storage.presigned_get(image.thumbnail_key or image.object_key),
        original_url=storage.presigned_get(image.object_key),
        best_similarity=best_similarity,
    )


def page_count(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))


def candidate_type(score: float, phash_distance: int | None) -> DuplicateType:
    if phash_distance is not None and phash_distance <= get_settings().perceptual_hash_threshold:
        return DuplicateType.PERCEPTUAL
    return DuplicateType.VISUAL
