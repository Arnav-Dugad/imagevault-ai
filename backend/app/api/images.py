import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, asc, desc, func, or_, select

from app.api.dependencies import CurrentUser, Database
from app.core.config import get_settings
from app.metrics import EXACT_DUPLICATES, IMAGE_UPLOADS, UPLOADED_BYTES
from app.models import (
    ActivityLog,
    DuplicateMatch,
    DuplicateType,
    Image,
    JobStatus,
    ProcessingJob,
    ProcessingStatus,
)
from app.schemas import (
    ImageDetail,
    ImageListResponse,
    MessageResponse,
    SimilarImage,
    UploadItem,
    UploadResponse,
)
from app.services.images import (
    image_summary,
    object_keys,
    page_count,
    read_validated_image,
    sha256_bytes,
    similarity_classification,
)
from app.services.storage import storage
from app.worker.tasks import process_image

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/images", tags=["Images"])
settings = get_settings()


async def owned_image(image_id: UUID, user_id: UUID, db: Database) -> Image:
    image = await db.scalar(select(Image).where(Image.id == image_id, Image.user_id == user_id))
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


async def similarity_map(image_ids: list[UUID], db: Database) -> dict[UUID, float]:
    if not image_ids:
        return {}
    rows = (
        await db.execute(
            select(
                DuplicateMatch.source_image_id,
                DuplicateMatch.target_image_id,
                DuplicateMatch.similarity_score,
            ).where(
                or_(
                    DuplicateMatch.source_image_id.in_(image_ids),
                    DuplicateMatch.target_image_id.in_(image_ids),
                )
            )
        )
    ).all()
    result: dict[UUID, float] = {}
    for source_id, target_id, score in rows:
        if source_id in image_ids:
            result[source_id] = max(result.get(source_id, 0), score)
        if target_id in image_ids:
            result[target_id] = max(result.get(target_id, 0), score)
    return result


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_images(
    user: CurrentUser,
    db: Database,
    files: Annotated[list[UploadFile], File(description="One or more JPG, PNG, or WebP files")],
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one image")
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=400, detail=f"A batch can contain at most {settings.max_batch_files} images"
        )

    response_items: list[UploadItem] = []
    queued_ids: list[UUID] = []
    stored_keys: list[str] = []
    try:
        for upload in files:
            data, filename, mime_type = await read_validated_image(upload)
            digest = sha256_bytes(data)
            duplicate = await db.scalar(
                select(Image)
                .where(Image.user_id == user.id, Image.sha256 == digest)
                .order_by(asc(Image.created_at))
                .limit(1)
            )
            image_id = uuid4()
            original_key, thumbnail_key = object_keys(user.id, image_id, mime_type)
            storage.put_bytes(original_key, data, mime_type)
            stored_keys.append(original_key)

            exact = duplicate is not None
            image = Image(
                id=image_id,
                user_id=user.id,
                original_filename=filename,
                object_key=original_key,
                thumbnail_key=thumbnail_key,
                mime_type=mime_type,
                file_size=len(data),
                sha256=digest,
                status=ProcessingStatus.EXACT_DUPLICATE if exact else ProcessingStatus.PENDING,
                exact_duplicate_of_id=duplicate.id if duplicate else None,
            )
            db.add(image)
            db.add(ProcessingJob(image_id=image_id, status=JobStatus.PENDING))
            db.add(
                ActivityLog(
                    user_id=user.id,
                    image_id=image_id,
                    action="image.uploaded",
                    details={"filename": filename, "exact_duplicate": exact},
                )
            )
            await db.flush()
            queued_ids.append(image_id)

            IMAGE_UPLOADS.inc()
            UPLOADED_BYTES.inc(len(data))
            if exact:
                EXACT_DUPLICATES.inc()
            response_items.append(
                UploadItem(
                    image=image_summary(image),
                    exact_duplicate=exact,
                    matched_filename=duplicate.original_filename if duplicate else None,
                    message=(
                        f"Exact duplicate detected: matches {duplicate.original_filename}"
                        if duplicate
                        else "Upload accepted and queued for private local processing"
                    ),
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        for key in stored_keys:
            try:
                storage.delete(key)
            except Exception:
                logger.exception("Failed to clean up object after upload rollback")
        raise

    for image_id in queued_ids:
        try:
            cast(Any, process_image).delay(str(image_id))
        except Exception:
            logger.exception("Unable to enqueue image", extra={"image_id": str(image_id)})
    return UploadResponse(items=response_items)


@router.get("", response_model=ImageListResponse)
async def list_images(
    user: CurrentUser,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    search: Annotated[str | None, Query(max_length=100)] = None,
    filter_by: Literal["all", "originals", "exact", "similar", "recent"] = "all",
    sort_by: Literal["newest", "oldest", "largest", "smallest", "filename"] = "newest",
) -> ImageListResponse:
    predicates = [Image.user_id == user.id]
    if search:
        predicates.append(Image.original_filename.ilike(f"%{search.strip()}%"))
    if filter_by == "originals":
        predicates.append(Image.exact_duplicate_of_id.is_(None))
    elif filter_by == "exact":
        predicates.append(Image.status == ProcessingStatus.EXACT_DUPLICATE)
    elif filter_by == "similar":
        match_ids = select(DuplicateMatch.source_image_id).where(
            DuplicateMatch.user_id == user.id,
            DuplicateMatch.match_type.in_([DuplicateType.VISUAL, DuplicateType.PERCEPTUAL]),
        )
        target_ids = select(DuplicateMatch.target_image_id).where(
            DuplicateMatch.user_id == user.id,
            DuplicateMatch.match_type.in_([DuplicateType.VISUAL, DuplicateType.PERCEPTUAL]),
        )
        predicates.append(or_(Image.id.in_(match_ids), Image.id.in_(target_ids)))
    elif filter_by == "recent":
        predicates.append(Image.created_at >= datetime.now(UTC) - timedelta(days=7))

    order = {
        "newest": desc(Image.created_at),
        "oldest": asc(Image.created_at),
        "largest": desc(Image.file_size),
        "smallest": asc(Image.file_size),
        "filename": asc(Image.original_filename),
    }[sort_by]
    where = and_(*predicates)
    total = int(await db.scalar(select(func.count()).select_from(Image).where(where)) or 0)
    images = list(
        (
            await db.scalars(
                select(Image)
                .where(where)
                .order_by(order)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    scores = await similarity_map([image.id for image in images], db)
    return ImageListResponse(
        items=[image_summary(image, scores.get(image.id)) for image in images],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


async def similar_for(image: Image, db: Database) -> list[SimilarImage]:
    matches = list(
        (
            await db.scalars(
                select(DuplicateMatch)
                .where(
                    DuplicateMatch.user_id == image.user_id,
                    or_(
                        DuplicateMatch.source_image_id == image.id,
                        DuplicateMatch.target_image_id == image.id,
                    ),
                )
                .order_by(desc(DuplicateMatch.similarity_score))
            )
        ).all()
    )
    candidate_ids = [
        match.target_image_id if match.source_image_id == image.id else match.source_image_id
        for match in matches
    ]
    candidates = {
        item.id: item
        for item in (
            (await db.scalars(select(Image).where(Image.id.in_(candidate_ids)))).all()
            if candidate_ids
            else []
        )
    }
    result: list[SimilarImage] = []
    for match, candidate_id in zip(matches, candidate_ids, strict=True):
        candidate = candidates.get(candidate_id)
        if candidate:
            result.append(
                SimilarImage(
                    image=image_summary(candidate, match.similarity_score),
                    similarity_score=match.similarity_score,
                    classification=similarity_classification(match.similarity_score),
                    match_type=match.match_type,
                    phash_distance=match.phash_distance,
                )
            )
    return result


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image(image_id: UUID, user: CurrentUser, db: Database) -> ImageDetail:
    image = await owned_image(image_id, user.id, db)
    duplicate = None
    if image.exact_duplicate_of_id:
        duplicate_image = await db.scalar(
            select(Image).where(
                Image.id == image.exact_duplicate_of_id, Image.user_id == user.id
            )
        )
        if duplicate_image:
            duplicate = image_summary(duplicate_image, 1.0)
    return ImageDetail(
        **image_summary(image).model_dump(),
        object_key=image.object_key,
        thumbnail_key=image.thumbnail_key,
        error_message=image.error_message,
        exif_timestamp=image.exif_timestamp,
        camera_model=image.camera_model,
        exact_duplicate_of=duplicate,
        similar_images=await similar_for(image, db),
    )


@router.get("/{image_id}/similar", response_model=list[SimilarImage])
async def get_similar(image_id: UUID, user: CurrentUser, db: Database) -> list[SimilarImage]:
    image = await owned_image(image_id, user.id, db)
    return await similar_for(image, db)


@router.delete("/{image_id}", response_model=MessageResponse)
async def delete_image(
    image_id: UUID,
    user: CurrentUser,
    db: Database,
    confirm: Annotated[bool, Query(description="Must be true; AI never deletes automatically")] = False,
) -> MessageResponse:
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit deletion confirmation is required")
    image = await owned_image(image_id, user.id, db)
    storage.delete(image.thumbnail_key)
    storage.delete(image.object_key)
    db.add(
        ActivityLog(
            user_id=user.id,
            action="image.deleted",
            details={"filename": image.original_filename, "sha256": image.sha256},
        )
    )
    await db.delete(image)
    await db.commit()
    return MessageResponse(message=f"Deleted {image.original_filename}")
