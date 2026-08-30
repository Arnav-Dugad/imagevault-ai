from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import desc, select

from app.api.dependencies import CurrentUser, Database
from app.models import DuplicateMatch, DuplicateType, Image, ProcessingStatus
from app.schemas import (
    DashboardResponse,
    DistributionPoint,
    DuplicateCandidate,
    DuplicateGroup,
    TimeSeriesPoint,
)
from app.services.images import image_summary, similarity_classification

router = APIRouter(tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(user: CurrentUser, db: Database) -> DashboardResponse:
    images = list(
        (await db.scalars(select(Image).where(Image.user_id == user.id).order_by(Image.created_at))).all()
    )
    visual_matches = list(
        (
            await db.scalars(
                select(DuplicateMatch).where(
                    DuplicateMatch.user_id == user.id,
                    DuplicateMatch.match_type.in_([DuplicateType.VISUAL, DuplicateType.PERCEPTUAL]),
                )
            )
        ).all()
    )
    exact = [image for image in images if image.exact_duplicate_of_id]
    similar_ids = {match.source_image_id for match in visual_matches} | {
        match.target_image_id for match in visual_matches
    }
    now = datetime.now(UTC)
    days = [(now - timedelta(days=offset)).date() for offset in range(6, -1, -1)]
    uploads_by_day: Counter = Counter(image.created_at.date() for image in images)
    duplicates_by_day: Counter = Counter(image.created_at.date() for image in exact)
    format_counts = Counter(image.mime_type.split("/")[-1].upper() for image in images)
    return DashboardResponse(
        total_images=len(images),
        unique_images=len(images) - len(exact),
        exact_duplicates=len(exact),
        similar_images=len(similar_ids),
        storage_used=sum(image.file_size for image in images),
        potential_savings=sum(image.file_size for image in exact),
        processing_images=sum(
            image.status in (ProcessingStatus.PENDING, ProcessingStatus.PROCESSING) for image in images
        ),
        uploads_over_time=[
            TimeSeriesPoint(
                label=day.strftime("%a"),
                uploads=uploads_by_day[day],
                duplicates=duplicates_by_day[day],
            )
            for day in days
        ],
        format_distribution=[
            DistributionPoint(name=name, value=value) for name, value in format_counts.items()
        ],
        recent_images=[image_summary(image) for image in reversed(images[-5:])],
    )


@router.get("/duplicates", response_model=list[DuplicateGroup])
async def duplicate_groups(user: CurrentUser, db: Database) -> list[DuplicateGroup]:
    images = list((await db.scalars(select(Image).where(Image.user_id == user.id))).all())
    by_id = {image.id: image for image in images}
    grouped: dict[UUID, list[DuplicateCandidate]] = defaultdict(list)

    for image in images:
        if image.exact_duplicate_of_id and image.exact_duplicate_of_id in by_id:
            grouped[image.exact_duplicate_of_id].append(
                DuplicateCandidate(
                    image=image_summary(image, 1.0),
                    similarity_score=1.0,
                    match_type=DuplicateType.EXACT,
                    classification="Exact Duplicate",
                )
            )

    matches = list(
        (
            await db.scalars(
                select(DuplicateMatch)
                .where(DuplicateMatch.user_id == user.id)
                .order_by(desc(DuplicateMatch.similarity_score))
            )
        ).all()
    )
    for match in matches:
        source = by_id.get(match.source_image_id)
        target = by_id.get(match.target_image_id)
        if not source or not target:
            continue
        original, candidate = (target, source) if target.created_at <= source.created_at else (source, target)
        if not any(item.image.id == candidate.id for item in grouped[original.id]):
            grouped[original.id].append(
                DuplicateCandidate(
                    image=image_summary(candidate, match.similarity_score),
                    similarity_score=match.similarity_score,
                    match_type=match.match_type,
                    classification=similarity_classification(match.similarity_score),
                )
            )

    return [
        DuplicateGroup(
            group_id=f"group-{str(original_id)[:8]}",
            original=image_summary(by_id[original_id]),
            candidates=sorted(items, key=lambda item: item.similarity_score, reverse=True),
            recoverable_bytes=sum(item.image.file_size for item in items),
        )
        for original_id, items in grouped.items()
        if items and original_id in by_id
    ]
