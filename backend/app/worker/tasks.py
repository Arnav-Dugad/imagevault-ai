import asyncio
import time
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

import imagehash
import structlog
from celery import signals
from PIL import ExifTags, Image as PillowImage
from prometheus_client import start_http_server
from redis import Redis
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db import SessionLocal
from app.metrics import (
    IMAGES_PROCESSED,
    PROCESSING_DURATION,
    PROCESSING_FAILURES,
    SIMILAR_IMAGES,
)
from app.models import (
    DuplicateMatch,
    DuplicateType,
    Image,
    JobStatus,
    ProcessingJob,
    ProcessingStatus,
)
from app.services.storage import storage
from app.worker.celery_app import celery_app
from app.worker.embedder import embedder

logger = structlog.get_logger("imagevault.worker")
settings = get_settings()


def _heartbeat() -> None:
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        redis.set("imagevault:worker:heartbeat", datetime.now(UTC).isoformat(), ex=30)
        redis.close()
    except Exception:
        logger.warning("worker_heartbeat_failed")


@signals.worker_process_init.connect
def start_worker_metrics(**_: object) -> None:
    start_http_server(settings.metrics_port)
    _heartbeat()


@signals.heartbeat_sent.connect
def heartbeat_sent(**_: object) -> None:
    _heartbeat()


def _thumbnail_and_metadata(data: bytes) -> tuple[bytes, int, int, str, datetime | None, str | None]:
    with PillowImage.open(BytesIO(data)) as source:
        width, height = source.size
        rgb = source.convert("RGB")
        perceptual_hash = str(imagehash.phash(rgb))
        exif_timestamp: datetime | None = None
        camera_model: str | None = None
        try:
            exif = source.getexif()
            model_value = exif.get(ExifTags.Base.Model.value)
            camera_model = str(model_value)[:200] if model_value else None
            date_value = exif.get(ExifTags.Base.DateTimeOriginal.value)
            if date_value:
                exif_timestamp = datetime.strptime(str(date_value), "%Y:%m:%d %H:%M:%S").replace(
                    tzinfo=UTC
                )
        except (ValueError, TypeError, AttributeError):
            pass
        rgb.thumbnail((640, 640), PillowImage.Resampling.LANCZOS)
        output = BytesIO()
        rgb.save(output, format="WEBP", quality=82, method=4)
        return output.getvalue(), width, height, perceptual_hash, exif_timestamp, camera_model


def _phash_distance(first: str | None, second: str | None) -> int | None:
    if not first or not second:
        return None
    try:
        return imagehash.hex_to_hash(first) - imagehash.hex_to_hash(second)
    except ValueError:
        return None


async def _set_running(image_id: UUID) -> Image | None:
    async with SessionLocal() as db:
        image = await db.get(Image, image_id)
        if image is None:
            return None
        image.status = (
            ProcessingStatus.EXACT_DUPLICATE
            if image.exact_duplicate_of_id
            else ProcessingStatus.PROCESSING
        )
        job = await db.scalar(select(ProcessingJob).where(ProcessingJob.image_id == image_id))
        if job:
            job.status = JobStatus.RUNNING
            job.attempts += 1
            job.started_at = datetime.now(UTC)
        await db.commit()
        return image


async def _save_result(
    image_id: UUID,
    *,
    width: int,
    height: int,
    perceptual_hash: str,
    exif_timestamp: datetime | None,
    camera_model: str | None,
    embedding: list[float] | None,
) -> int:
    matches_created = 0
    async with SessionLocal() as db:
        image = await db.get(Image, image_id)
        if image is None:
            return 0
        image.width = width
        image.height = height
        image.perceptual_hash = perceptual_hash
        image.exif_timestamp = exif_timestamp
        image.camera_model = camera_model
        image.embedding = embedding
        image.processed_at = datetime.now(UTC)

        if image.exact_duplicate_of_id:
            original = await db.get(Image, image.exact_duplicate_of_id)
            if original:
                image.embedding = original.embedding
            image.status = ProcessingStatus.EXACT_DUPLICATE
        else:
            image.status = ProcessingStatus.READY
            await db.flush()
            if embedding:
                distance = Image.embedding.cosine_distance(embedding).label("distance")
                nearest = (
                    await db.execute(
                        select(Image, distance)
                        .where(
                            Image.user_id == image.user_id,
                            Image.id != image.id,
                            Image.embedding.is_not(None),
                            Image.status.in_(
                                [ProcessingStatus.READY, ProcessingStatus.EXACT_DUPLICATE]
                            ),
                        )
                        .order_by(distance)
                        .limit(10)
                    )
                ).all()
                await db.execute(
                    delete(DuplicateMatch).where(DuplicateMatch.source_image_id == image.id)
                )
                for candidate, cosine_distance in nearest:
                    score = max(-1.0, min(1.0, 1.0 - float(cosine_distance)))
                    phash_distance = _phash_distance(perceptual_hash, candidate.perceptual_hash)
                    perceptual = (
                        phash_distance is not None
                        and phash_distance <= settings.perceptual_hash_threshold
                    )
                    if score < settings.visual_similarity_threshold and not perceptual:
                        continue
                    db.add(
                        DuplicateMatch(
                            user_id=image.user_id,
                            source_image_id=image.id,
                            target_image_id=candidate.id,
                            match_type=(DuplicateType.PERCEPTUAL if perceptual else DuplicateType.VISUAL),
                            similarity_score=score,
                            phash_distance=phash_distance,
                        )
                    )
                    matches_created += 1

        job = await db.scalar(select(ProcessingJob).where(ProcessingJob.image_id == image_id))
        if job:
            job.status = JobStatus.COMPLETE
            job.completed_at = datetime.now(UTC)
            job.error_message = None
        await db.commit()
    return matches_created


async def _mark_failed(image_id: UUID, message: str) -> None:
    async with SessionLocal() as db:
        image = await db.get(Image, image_id)
        if image:
            image.status = ProcessingStatus.FAILED
            image.error_message = message[:1000]
        job = await db.scalar(select(ProcessingJob).where(ProcessingJob.image_id == image_id))
        if job:
            job.status = JobStatus.FAILED
            job.error_message = message[:1000]
            job.completed_at = datetime.now(UTC)
        await db.commit()


async def _process(image_id: UUID) -> dict[str, object]:
    started = time.perf_counter()
    image = await _set_running(image_id)
    if image is None:
        return {"status": "missing", "image_id": str(image_id)}
    try:
        data = storage.get_bytes(image.object_key)
        thumbnail, width, height, phash, exif_time, camera = _thumbnail_and_metadata(data)
        storage.put_bytes(image.thumbnail_key, thumbnail, "image/webp")
        embedding: list[float] | None = None
        device = "reused"
        inference_seconds = 0.0
        if not image.exact_duplicate_of_id:
            embedding, inference_seconds, device = embedder.image_embedding(data)
        matches = await _save_result(
            image_id,
            width=width,
            height=height,
            perceptual_hash=phash,
            exif_timestamp=exif_time,
            camera_model=camera,
            embedding=embedding,
        )
        duration = time.perf_counter() - started
        IMAGES_PROCESSED.inc()
        SIMILAR_IMAGES.inc(matches)
        PROCESSING_DURATION.observe(duration)
        _heartbeat()
        logger.info(
            "image_processed",
            image_id=str(image_id),
            duration_ms=round(duration * 1000, 2),
            inference_ms=round(inference_seconds * 1000, 2),
            device=device,
            matches=matches,
        )
        return {
            "status": "complete",
            "image_id": str(image_id),
            "duration_seconds": duration,
            "matches": matches,
            "device": device,
        }
    except Exception as exc:
        PROCESSING_FAILURES.inc()
        await _mark_failed(image_id, str(exc))
        logger.exception("image_processing_failed", image_id=str(image_id), error=str(exc))
        raise


@celery_app.task(
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
    name="imagevault.process_image",
)
def process_image(self, image_id: str) -> dict[str, object]:
    del self
    return asyncio.run(_process(UUID(image_id)))
