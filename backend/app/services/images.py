import hashlib
import math
import re
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

from app.core.config import get_settings
from app.models import DuplicateType, Image, MediaKind
from app.schemas import ImageSummary
from app.services.storage import storage

PillowImage.MAX_IMAGE_PIXELS = 50_000_000

MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/x-adobe-dng": ".dng",
    "image/x-canon-cr2": ".cr2",
    "image/x-nikon-nef": ".nef",
    "image/x-sony-arw": ".arw",
    "image/x-raw": ".raw",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
}

EXTENSION_MIME_TYPES = {extension: mime for mime, extension in MIME_EXTENSIONS.items()}
RAW_MIME_TYPES = {mime for mime in MIME_EXTENSIONS if mime.startswith("image/x-")}
VIDEO_MIME_TYPES = {mime for mime in MIME_EXTENSIONS if mime.startswith("video/")}
BROWSER_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def media_kind_for(mime_type: str, *, frame_count: int = 1) -> MediaKind:
    if mime_type in VIDEO_MIME_TYPES:
        return MediaKind.VIDEO
    if mime_type in RAW_MIME_TYPES:
        return MediaKind.RAW
    if mime_type == "image/gif" or frame_count > 1:
        return MediaKind.ANIMATED_IMAGE
    return MediaKind.PHOTO


def _detected_mime(data: bytes, filename: str) -> str | None:
    head = data[:4096]
    suffix = Path(filename).suffix.casefold()
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"RIFF") and head[8:12] == b"AVI ":
        return "video/x-msvideo"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm" if b"webm" in head.lower() else "video/x-matroska"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12].lower()
        if brand in {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}:
            return "image/heif" if suffix == ".heif" else "image/heic"
        if brand == b"qt  ":
            return "video/quicktime"
        return "video/mp4"
    tiff_header = head.startswith((b"II*\x00", b"MM\x00*"))
    if tiff_header and suffix in {".dng", ".cr2", ".nef", ".arw", ".raw"}:
        return EXTENSION_MIME_TYPES[suffix]
    return None


async def read_validated_image(upload: UploadFile) -> tuple[bytes, str, str]:
    settings = get_settings()
    declared_mime = (upload.content_type or "").lower()
    filename = upload.filename or "upload"
    suffix_mime = EXTENSION_MIME_TYPES.get(Path(filename).suffix.casefold())
    hinted_mime = declared_mime if declared_mime in settings.allowed_mime_types else suffix_mime
    if hinted_mime not in settings.allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: {declared_mime or Path(filename).suffix or 'unknown'}",
        )

    chunks: list[bytes] = []
    size = 0
    limit = (
        settings.max_video_upload_bytes
        if hinted_mime in VIDEO_MIME_TYPES or hinted_mime in RAW_MIME_TYPES
        else settings.max_upload_bytes
    )
    while chunk := await upload.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{upload.filename or 'Media'} exceeds the upload limit",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Empty files cannot be uploaded")

    detected_mime = _detected_mime(data, filename)
    if detected_mime is None or detected_mime not in settings.allowed_mime_types:
        raise HTTPException(status_code=400, detail="The file is not a supported image or video")
    if declared_mime in settings.allowed_mime_types and declared_mime != detected_mime:
        compatible_heif = {declared_mime, detected_mime} <= {"image/heic", "image/heif"}
        compatible_raw = declared_mime in RAW_MIME_TYPES and detected_mime in RAW_MIME_TYPES
        if not compatible_heif and not compatible_raw:
            raise HTTPException(status_code=400, detail="Declared media type does not match file content")
    if detected_mime in BROWSER_IMAGE_MIME_TYPES:
        try:
            with PillowImage.open(BytesIO(data)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, PillowImage.DecompressionBombError) as exc:
            raise HTTPException(status_code=400, detail="The file is not a valid image") from exc

    safe_name = safe_filename(filename or f"upload{MIME_EXTENSIONS[detected_mime]}")
    return data, safe_name, detected_mime


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
        batch_id=image.batch_id,
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
        thumbnail_url=(
            storage.presigned_get(image.thumbnail_key)
            if image.thumbnail_key and image.processed_at
            else None
        ),
        original_url=storage.presigned_get(image.object_key),
        best_similarity=best_similarity,
        blur_score=image.blur_score,
        exposure_score=image.exposure_score,
        resolution_score=image.resolution_score,
        screenshot_quality_score=image.screenshot_quality_score,
        quality_score=image.quality_score,
        is_screenshot=image.is_screenshot,
        smart_labels=image.smart_labels or [],
        face_count=image.face_count,
        media_kind=image.media_kind,
        frame_count=image.frame_count,
        duration_seconds=image.duration_seconds,
        processing_device=image.processing_device,
    )


def page_count(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))


def candidate_type(score: float, phash_distance: int | None) -> DuplicateType:
    if phash_distance is not None and phash_distance <= get_settings().perceptual_hash_threshold:
        return DuplicateType.PERCEPTUAL
    return DuplicateType.VISUAL
