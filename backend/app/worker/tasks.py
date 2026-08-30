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
from sqlalchemy import delete, or_, select

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
from app.services.similarity import cosine_similarity, evaluate_similarity, hash_distance
from app.services.storage import storage
from app.worker.celery_app import celery_app
from app.worker.embedder import embedder

logger = structlog.get_logger("imagevault.worker")
settings = get_settings()
_worker_runner: asyncio.Runner | None = None


def _get_worker_runner() -> asyncio.Runner:
    """Return the process-local runner used by every Celery task.

    SQLAlchemy's asyncpg connections belong to the event loop that created
    them. Creating a fresh loop with ``asyncio.run`` for every task lets the
    connection pool hand a later task a connection from a closed loop. A
    long-lived runner keeps all tasks and pooled connections on one loop.
    """
    global _worker_runner
    if _worker_runner is None:
        _worker_runner = asyncio.Runner()
        _worker_runner.get_loop()
    return _worker_runner


def _heartbeat() -> None:
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        redis.set("imagevault:worker:heartbeat", datetime.now(UTC).isoformat(), ex=30)
        redis.close()
    except Exception:
        logger.warning("worker_heartbeat_failed")


@signals.worker_process_init.connect
def start_worker_metrics(**_: object) -> None:
    _get_worker_runner()
    start_http_server(settings.metrics_port)
    _heartbeat()


@signals.worker_process_shutdown.connect
def close_worker_resources(**_: object) -> None:
    global _worker_runner
    if _worker_runner is None:
        return
    from app.db import engine

    try:
        _worker_runner.run(engine.dispose())
    finally:
        _worker_runner.close()
        _worker_runner = None


@signals.heartbeat_sent.connect
def heartbeat_sent(**_: object) -> None:
    _heartbeat()


def _color_signature(image: PillowImage.Image) -> list[float]:
    sample = image.resize((64, 64), PillowImage.Resampling.LANCZOS)
    histogram = sample.histogram()
    pixels = float(sample.width * sample.height)
    signature: list[float] = []
    for channel in range(3):
        values = histogram[channel * 256 : (channel + 1) * 256]
        signature.extend(sum(values[index : index + 32]) / pixels for index in range(0, 256, 32))
    return signature


def _thumbnail_and_metadata(
    data: bytes,
) -> tuple[
    bytes,
    int,
    int,
    str,
    str,
    str,
    list[float],
    datetime | None,
    str | None,
]:
    with PillowImage.open(BytesIO(data)) as source:
        width, height = source.size
        rgb = source.convert("RGB")
        perceptual_hash = str(imagehash.phash(rgb))
        difference_hash = str(imagehash.dhash(rgb))
        wavelet_hash = str(imagehash.whash(rgb))
        color_signature = _color_signature(rgb)
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
        return (
            output.getvalue(),
            width,
            height,
            perceptual_hash,
            difference_hash,
            wavelet_hash,
            color_signature,
            exif_timestamp,
            camera_model,
        )


def _phash_distance(first: str | None, second: str | None) -> int | None:
    return hash_distance(first, second)


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
    difference_hash: str,
    wavelet_hash: str,
    color_signature: list[float],
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
        image.difference_hash = difference_hash
        image.wavelet_hash = wavelet_hash
        image.color_signature = color_signature
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
                        .limit(settings.similarity_candidate_limit)
                    )
                ).all()

                candidate_map: dict[UUID, tuple[Image, float]] = {
                    candidate.id: (candidate, max(-1.0, min(1.0, 1.0 - float(cosine_distance))))
                    for candidate, cosine_distance in nearest
                }
                fingerprint_rows = (
                    await db.execute(
                        select(
                            Image.id,
                            Image.perceptual_hash,
                            Image.difference_hash,
                            Image.wavelet_hash,
                        ).where(
                            Image.user_id == image.user_id,
                            Image.id != image.id,
                            Image.status.in_(
                                [ProcessingStatus.READY, ProcessingStatus.EXACT_DUPLICATE]
                            ),
                        )
                    )
                ).all()
                perceptual_ids: list[UUID] = []
                for candidate_id, phash, dhash, whash in fingerprint_rows:
                    distances = [
                        value
                        for value in (
                            hash_distance(perceptual_hash, phash),
                            hash_distance(difference_hash, dhash),
                            hash_distance(wavelet_hash, whash),
                        )
                        if value is not None
                    ]
                    if distances and min(distances) <= settings.perceptual_prefilter_distance:
                        perceptual_ids.append(candidate_id)
                    if len(perceptual_ids) >= settings.similarity_candidate_limit:
                        break

                missing_ids = [candidate_id for candidate_id in perceptual_ids if candidate_id not in candidate_map]
                if missing_ids:
                    for candidate in (
                        await db.scalars(select(Image).where(Image.id.in_(missing_ids)))
                    ).all():
                        candidate_map[candidate.id] = (
                            candidate,
                            cosine_similarity(embedding, candidate.embedding),
                        )

                await db.execute(
                    delete(DuplicateMatch).where(
                        or_(
                            DuplicateMatch.source_image_id == image.id,
                            DuplicateMatch.target_image_id == image.id,
                        )
                    )
                )
                for candidate, clip_score in candidate_map.values():
                    evidence = evaluate_similarity(
                        first_hashes=(perceptual_hash, difference_hash, wavelet_hash),
                        second_hashes=(
                            candidate.perceptual_hash,
                            candidate.difference_hash,
                            candidate.wavelet_hash,
                        ),
                        first_color=color_signature,
                        second_color=candidate.color_signature,
                        first_size=(width, height),
                        second_size=(candidate.width, candidate.height),
                        clip_score=clip_score,
                        perceptual_hash_threshold=settings.perceptual_hash_threshold,
                        visual_similarity_threshold=settings.visual_similarity_threshold,
                    )
                    if evidence is None:
                        continue
                    source_id, target_id = sorted((image.id, candidate.id), key=str)
                    db.add(
                        DuplicateMatch(
                            user_id=image.user_id,
                            source_image_id=source_id,
                            target_image_id=target_id,
                            match_type=DuplicateType(evidence.match_type),
                            similarity_score=evidence.score,
                            phash_distance=evidence.phash_distance,
                            clip_score=evidence.clip_score,
                            perceptual_score=evidence.perceptual_score,
                            color_score=evidence.color_score,
                            aspect_score=evidence.aspect_score,
                            evidence=evidence.reasons,
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
        (
            thumbnail,
            width,
            height,
            phash,
            dhash,
            whash,
            color_signature,
            exif_time,
            camera,
        ) = _thumbnail_and_metadata(data)
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
            difference_hash=dhash,
            wavelet_hash=whash,
            color_signature=color_signature,
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
    return _get_worker_runner().run(_process(UUID(image_id)))
