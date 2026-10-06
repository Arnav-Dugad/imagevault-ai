from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from app.api.dependencies import CurrentUser, Database
from app.services.matches import current_match_predicates
from app.models import DuplicateMatch, DuplicateType, Image
from app.schemas import (
    DashboardResponse,
    DistributionPoint,
    DuplicateCandidate,
    DuplicateGroup,
    DuplicateReviewResponse,
    TimeSeriesPoint,
)
from app.core.config import get_settings
from app.services.images import analysis_pending, image_summary, similarity_classification

router = APIRouter(tags=["Analytics"])


@dataclass(frozen=True)
class GroupEdge:
    match_type: DuplicateType
    score: float
    phash_distance: int | None = None
    clip_score: float | None = None
    perceptual_score: float | None = None
    color_score: float | None = None
    aspect_score: float | None = None
    reasons: tuple[str, ...] = ()


def _pair(first: UUID, second: UUID) -> tuple[UUID, UUID]:
    return tuple(sorted((first, second), key=str))  # type: ignore[return-value]


def _keeper_key(image: Image) -> tuple[bool, int, int, datetime]:
    pixels = (image.width or 0) * (image.height or 0)
    return image.exact_duplicate_of_id is not None, -pixels, -image.file_size, image.created_at


async def _duplicate_groups(
    user_id: UUID,
    db: Database,
    batch_id: UUID | None = None,
) -> tuple[list[DuplicateGroup], list[Image]]:
    images = list((await db.scalars(select(Image).where(Image.user_id == user_id))).all())
    by_id = {image.id: image for image in images}
    scoped_ids = {image.id for image in images if batch_id is None or image.batch_id == batch_id}
    edges: dict[tuple[UUID, UUID], GroupEdge] = {}

    def connect(first: UUID, second: UUID, edge: GroupEdge) -> None:
        if first == second or first not in by_id or second not in by_id:
            return
        if batch_id is not None and first not in scoped_ids and second not in scoped_ids:
            return
        key = _pair(first, second)
        current = edges.get(key)
        if current is None or edge.match_type == DuplicateType.EXACT or edge.score > current.score:
            edges[key] = edge

    exact_families: dict[str, list[Image]] = defaultdict(list)
    for image in images:
        exact_families[image.sha256].append(image)
    for family in exact_families.values():
        for first, second in combinations(family, 2):
            connect(
                first.id,
                second.id,
                GroupEdge(
                    match_type=DuplicateType.EXACT,
                    score=1.0,
                    phash_distance=0,
                    clip_score=1.0,
                    perceptual_score=1.0,
                    color_score=1.0,
                    aspect_score=1.0,
                    reasons=("Byte-for-byte SHA-256 match",),
                ),
            )

    matches = list(
        (
            await db.scalars(
                select(DuplicateMatch)
                .where(DuplicateMatch.user_id == user_id, *current_match_predicates())
                .order_by(desc(DuplicateMatch.similarity_score))
            )
        ).all()
    )
    for match in matches:
        # Hide stale, unverified matches until the user upgrades the index.
        if any(by_id.get(image_id) is None or by_id[image_id].analysis_version < get_settings().analysis_version
               for image_id in (match.source_image_id, match.target_image_id)):
            continue
        evidence = GroupEdge(
            match_type=match.match_type,
            score=match.similarity_score,
            phash_distance=match.phash_distance,
            clip_score=match.clip_score,
            perceptual_score=match.perceptual_score,
            color_score=match.color_score,
            aspect_score=match.aspect_score,
            reasons=tuple(match.evidence or ()),
        )
        # A byte-identical copy has the same visual evidence. Share only across
        # SHA-256 equivalence, never across a merely similar-image chain.
        for first in exact_families[by_id[match.source_image_id].sha256]:
            for second in exact_families[by_id[match.target_image_id].sha256]:
                connect(first.id, second.id, evidence)

    # Complete-link families: every member has direct evidence against every
    # other member. A-B and B-C alone never establish an A-C duplicate.
    active_ids = {image_id for pair in edges for image_id in pair}
    components = {image_id: {image_id} for image_id in active_ids}
    owner = {image_id: image_id for image_id in active_ids}
    for (first, second), _ in sorted(edges.items(), key=lambda item: (-item[1].score, str(item[0]))):
        left, right = owner[first], owner[second]
        if left == right:
            continue
        if not all(_pair(a, b) in edges for a in components[left] for b in components[right]):
            continue
        components[left].update(components.pop(right))
        for image_id in components[left]:
            owner[image_id] = left

    groups: list[DuplicateGroup] = []
    for member_ids in components.values():
        if len(member_ids) < 2:
            continue
        members = [by_id[member_id] for member_id in member_ids]
        keeper = min(members, key=_keeper_key)
        candidates: list[DuplicateCandidate] = []
        for candidate in sorted(
            (item for item in members if item.id != keeper.id),
            key=_keeper_key,
        ):
            evidence = edges[_pair(keeper.id, candidate.id)]
            reasons = list(evidence.reasons)
            candidates.append(
                DuplicateCandidate(
                    image=image_summary(candidate, evidence.score),
                    similarity_score=evidence.score,
                    match_type=evidence.match_type,
                    classification=(
                        "Exact Duplicate"
                        if evidence.match_type == DuplicateType.EXACT
                        else similarity_classification(evidence.score)
                    ),
                    phash_distance=evidence.phash_distance,
                    clip_score=evidence.clip_score,
                    perceptual_score=evidence.perceptual_score,
                    color_score=evidence.color_score,
                    aspect_score=evidence.aspect_score,
                    reasons=reasons,
                    same_batch=bool(keeper.batch_id and keeper.batch_id == candidate.batch_id),
                )
            )
        groups.append(
            DuplicateGroup(
                group_id=f"family-{str(min(member_ids, key=str))[:8]}",
                original=image_summary(keeper),
                candidates=sorted(candidates, key=lambda item: item.similarity_score, reverse=True),
                recoverable_bytes=sum(item.image.file_size for item in candidates),
                highest_similarity=max(item.similarity_score for item in candidates),
                all_same_batch=bool(
                    keeper.batch_id and all(item.batch_id == keeper.batch_id for item in members)
                ),
            )
        )
    groups.sort(key=lambda group: (group.highest_similarity, group.recoverable_bytes), reverse=True)
    scoped_images = [image for image in images if image.id in scoped_ids]
    return groups, scoped_images


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
                    *current_match_predicates(),
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
            analysis_pending(image) for image in images
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
    groups, _ = await _duplicate_groups(user.id, db)
    return groups


@router.get("/duplicates/review", response_model=DuplicateReviewResponse)
async def duplicate_review(
    user: CurrentUser,
    db: Database,
    batch_id: Annotated[UUID | None, Query()] = None,
) -> DuplicateReviewResponse:
    groups, scoped_images = await _duplicate_groups(user.id, db, batch_id)
    candidates = [candidate for group in groups for candidate in group.candidates]
    return DuplicateReviewResponse(
        groups=groups,
        batch_id=batch_id,
        total_groups=len(groups),
        exact_duplicates=sum(item.match_type == DuplicateType.EXACT for item in candidates),
        similar_images=len(
            {item.image.id for item in candidates if item.match_type != DuplicateType.EXACT}
        ),
        recoverable_bytes=sum(group.recoverable_bytes for group in groups),
        processing_images=sum(
            analysis_pending(image)
            for image in scoped_images
        ),
        total_images_scanned=len(scoped_images),
    )
