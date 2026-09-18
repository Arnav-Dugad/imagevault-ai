import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, asc, desc, func, or_, select

from starlette.concurrency import run_in_threadpool

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
    BulkDeleteRequest,
    BulkDeleteResponse,
    ImageDetail,
    ImageListResponse,
    MessageResponse,
    ReindexResponse,
    SimilarImage,
    UploadItem,
    UploadResponse,
)
from app.services.images import (
    image_summary,
    media_kind_for,
    object_keys,
    page_count,
    read_validated_image,
    sha256_bytes,
    similarity_classification,
)
from app.services.storage import storage
from app.worker.tasks import embed_text, process_image

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
    files: Annotated[list[UploadFile], File(description="One or more supported photos or videos")],
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one image")
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=400, detail=f"A batch can contain at most {settings.max_batch_files} images"
        )

    response_items: list[UploadItem] = []
    batch_id = uuid4()
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
            await run_in_threadpool(storage.put_bytes, original_key, data, mime_type)
            stored_keys.append(original_key)

            exact = duplicate is not None
            image = Image(
                id=image_id,
                user_id=user.id,
                batch_id=batch_id,
                original_filename=filename,
                object_key=original_key,
                thumbnail_key=thumbnail_key,
                mime_type=mime_type,
                media_kind=media_kind_for(mime_type),
                file_size=len(data),
                sha256=digest,
                status=ProcessingStatus.EXACT_DUPLICATE if exact else ProcessingStatus.PENDING,
                exact_duplicate_of_id=duplicate.id if duplicate else None,
            )
            db.add(image)
            # The job and activity log reference this image by foreign key. Flush the
            # parent row first because those models do not have ORM relationships that
            # let SQLAlchemy infer the required INSERT ordering.
            await db.flush()
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
                await run_in_threadpool(storage.delete, key)
            except Exception:
                logger.exception("Failed to clean up object after upload rollback")
        raise

    for image_id in queued_ids:
        try:
            cast(Any, process_image).delay(str(image_id))
        except Exception:
            logger.exception("Unable to enqueue image", extra={"image_id": str(image_id)})
    return UploadResponse(batch_id=batch_id, items=response_items)


@router.get("", response_model=ImageListResponse)
async def list_images(
    user: CurrentUser,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    search: Annotated[str | None, Query(max_length=100)] = None,
    filter_by: Literal["all", "originals", "exact", "similar", "recent"] = "all",
    sort_by: Literal["newest", "oldest", "largest", "smallest", "filename", "quality"] = "newest",
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
        "quality": desc(Image.quality_score).nullslast(),
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


@router.post("/reindex", response_model=ReindexResponse, status_code=status.HTTP_202_ACCEPTED)
async def reindex_images(
    user: CurrentUser,
    db: Database,
    missing_only: Annotated[
        bool,
        Query(description="Only rebuild images that do not have the premium multi-signal index"),
    ] = True,
) -> ReindexResponse:
    images = list(
        (
            await db.scalars(
                select(Image)
                .where(Image.user_id == user.id)
                .order_by(asc(Image.created_at))
            )
        ).all()
    )
    queued: list[UUID] = []
    for image in sorted(images, key=lambda item: item.exact_duplicate_of_id is not None):
        has_smart_index = bool(
            image.analysis_version >= settings.analysis_version
            and image.difference_hash
            and image.wavelet_hash
            and image.color_signature
            and image.quality_score is not None
        )
        if missing_only and has_smart_index:
            continue
        if image.status in (ProcessingStatus.PENDING, ProcessingStatus.PROCESSING):
            continue
        image.status = (
            ProcessingStatus.EXACT_DUPLICATE
            if image.exact_duplicate_of_id
            else ProcessingStatus.PENDING
        )
        image.error_message = None
        job = await db.scalar(select(ProcessingJob).where(ProcessingJob.image_id == image.id))
        if job:
            job.status = JobStatus.PENDING
            job.error_message = None
            job.started_at = None
            job.completed_at = None
        else:
            db.add(ProcessingJob(image_id=image.id, status=JobStatus.PENDING))
        queued.append(image.id)
    await db.commit()

    for image_id in queued:
        try:
            cast(Any, process_image).delay(str(image_id))
        except Exception:
            logger.exception("Unable to enqueue reindex", extra={"image_id": str(image_id)})
    return ReindexResponse(
        queued=len(queued),
        message=(
            f"Queued {len(queued)} image{'s' if len(queued) != 1 else ''} for smart re-analysis"
            if queued
            else "Every image already has the latest smart index"
        ),
    )


@router.get("/smart-search", response_model=ImageListResponse)
async def smart_search(
    user: CurrentUser,
    db: Database,
    query: Annotated[str, Query(min_length=2, max_length=500)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> ImageListResponse:
    cleaned = " ".join(query.split())
    task = cast(Any, embed_text).delay(cleaned)
    try:
        vector = await asyncio.to_thread(
            task.get,
            timeout=settings.semantic_search_timeout_seconds,
            disable_sync_subtasks=False,
        )
    except Exception as exc:
        logger.exception("Semantic search embedding failed")
        raise HTTPException(
            status_code=503,
            detail="Smart search is warming up. Try again in a few seconds.",
        ) from exc
    finally:
        try:
            task.forget()
        except Exception:
            pass

    result_scores: dict[UUID, float] = {}
    result_images: dict[UUID, Image] = {}
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        distance = Image.embedding.cosine_distance(vector).label("distance")
        rows = (
            await db.execute(
                select(Image, distance)
                .where(
                    Image.user_id == user.id,
                    Image.embedding.is_not(None),
                    Image.status.in_([ProcessingStatus.READY, ProcessingStatus.EXACT_DUPLICATE]),
                )
                .order_by(distance)
                .limit(200)
            )
        ).all()
        for image, cosine_distance in rows:
            raw_score = max(-1.0, min(1.0, 1.0 - float(cosine_distance)))
            if raw_score < settings.semantic_search_min_score:
                continue
            result_images[image.id] = image
            result_scores[image.id] = max(0.01, min(1.0, (raw_score - 0.10) / 0.22))

    tokens = [token for token in cleaned.split() if len(token) >= 3][:8]
    text_predicates = [
        Image.original_filename.ilike(f"%{cleaned}%"),
        Image.ocr_text.ilike(f"%{cleaned}%"),
    ]
    text_predicates.extend(Image.ocr_text.ilike(f"%{token}%") for token in tokens)
    text_matches = list(
        (
            await db.scalars(
                select(Image)
                .where(
                    Image.user_id == user.id,
                    Image.status.in_([ProcessingStatus.READY, ProcessingStatus.EXACT_DUPLICATE]),
                    or_(*text_predicates),
                )
                .limit(200)
            )
        ).all()
    )
    query_folded = cleaned.casefold()
    for image in text_matches:
        filename_match = query_folded in image.original_filename.casefold()
        ocr = (image.ocr_text or "").casefold()
        complete_ocr_match = query_folded in ocr
        token_ratio = sum(token.casefold() in ocr for token in tokens) / max(1, len(tokens))
        text_score = 0.99 if filename_match else 0.94 if complete_ocr_match else 0.62 + token_ratio * 0.25
        result_images[image.id] = image
        result_scores[image.id] = max(result_scores.get(image.id, 0), text_score)

    ranked = sorted(result_images.values(), key=lambda image: result_scores[image.id], reverse=True)
    total = len(ranked)
    start = (page - 1) * page_size
    visible = ranked[start : start + page_size]
    return ImageListResponse(
        items=[image_summary(image, result_scores[image.id]) for image in visible],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_images(
    request: BulkDeleteRequest,
    user: CurrentUser,
    db: Database,
) -> BulkDeleteResponse:
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit deletion confirmation is required")
    image_ids = list(dict.fromkeys(request.image_ids))
    images = list(
        (
            await db.scalars(
                select(Image).where(Image.user_id == user.id, Image.id.in_(image_ids))
            )
        ).all()
    )
    if len(images) != len(image_ids):
        raise HTTPException(status_code=404, detail="One or more images were not found")

    recovered_bytes = sum(image.file_size for image in images)
    for image in images:
        await run_in_threadpool(storage.delete, image.thumbnail_key)
        await run_in_threadpool(storage.delete, image.object_key)
    db.add(
        ActivityLog(
            user_id=user.id,
            action="images.bulk_deleted",
            details={
                "count": len(images),
                "recovered_bytes": recovered_bytes,
                "filenames": [image.original_filename for image in images],
            },
        )
    )
    for image in images:
        await db.delete(image)
    await db.commit()
    return BulkDeleteResponse(
        deleted=len(images),
        recovered_bytes=recovered_bytes,
        message=f"Deleted {len(images)} image{'s' if len(images) != 1 else ''}",
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
                    clip_score=match.clip_score,
                    perceptual_score=match.perceptual_score,
                    color_score=match.color_score,
                    aspect_score=match.aspect_score,
                    reasons=match.evidence or [],
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
        ocr_text=image.ocr_text,
        ocr_language=image.ocr_language,
        ocr_layout=image.ocr_layout or [],
        document_type=image.document_type,
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
    await run_in_threadpool(storage.delete, image.thumbnail_key)
    await run_in_threadpool(storage.delete, image.object_key)
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
