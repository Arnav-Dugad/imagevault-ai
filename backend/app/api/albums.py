from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import desc, or_, select

from app.api.dependencies import CurrentUser, Database
from app.core.config import get_settings
from app.models import DetectedFace, DuplicateMatch, DuplicateType, Image, ProcessingStatus
from app.schemas import SmartAlbum, SmartAlbumsResponse
from app.services.albums import best_photo, cluster_faces, group_bursts, group_events, image_time
from app.services.images import image_summary

router = APIRouter(prefix="/albums", tags=["Smart albums"])
settings = get_settings()


async def library_context(
    user_id: UUID, db: Database
) -> tuple[list[Image], set[frozenset[UUID]]]:
    images = list(
        (
            await db.scalars(
                select(Image)
                .where(
                    Image.user_id == user_id,
                    Image.status == ProcessingStatus.READY,
                )
                .order_by(desc(Image.created_at))
            )
        ).all()
    )
    image_ids = {image.id for image in images}
    matches = list(
        (
            await db.scalars(
                select(DuplicateMatch).where(
                    DuplicateMatch.user_id == user_id,
                    DuplicateMatch.match_type.in_([DuplicateType.PERCEPTUAL, DuplicateType.VISUAL]),
                    DuplicateMatch.similarity_score >= 0.78,
                )
            )
        ).all()
    )
    edges = {
        frozenset((match.source_image_id, match.target_image_id))
        for match in matches
        if match.source_image_id in image_ids and match.target_image_id in image_ids
    }
    return images, edges


def album_payload(
    album_id: str,
    title: str,
    subtitle: str,
    images: list[Image],
) -> SmartAlbum:
    keeper = best_photo(images)
    return SmartAlbum(
        id=album_id,
        title=title,
        subtitle=subtitle,
        cover=image_summary(keeper),
        images=[image_summary(image) for image in images[:24]],
        image_count=len(images),
        best_image_id=keeper.id,
    )


@router.get("/events", response_model=SmartAlbumsResponse)
async def event_albums(user: CurrentUser, db: Database) -> SmartAlbumsResponse:
    images, edges = await library_context(user.id, db)
    groups = group_events(images, edges, gap_hours=settings.event_gap_hours)
    albums: list[SmartAlbum] = []
    for index, group in enumerate(groups[:50]):
        start, end = image_time(group[0]), image_time(group[-1])
        title = start.strftime("%B %d, %Y")
        cameras = sorted({image.camera_model for image in group if image.camera_model})
        time_range = start.strftime("%I:%M %p").lstrip("0")
        if end != start:
            time_range += f" – {end.strftime('%I:%M %p').lstrip('0')}"
        subtitle = time_range + (f" · {cameras[0]}" if len(cameras) == 1 else "")
        albums.append(album_payload(f"event-{start.isoformat()}-{index}", title, subtitle, group))
    return SmartAlbumsResponse(items=albums, total=len(albums))


@router.get("/bursts", response_model=SmartAlbumsResponse)
async def burst_albums(user: CurrentUser, db: Database) -> SmartAlbumsResponse:
    images, edges = await library_context(user.id, db)
    groups = group_bursts(images, edges, gap_seconds=settings.burst_gap_seconds)
    albums = [
        album_payload(
            f"burst-{image_time(group[0]).isoformat()}-{index}",
            f"Burst · {image_time(group[0]).strftime('%b %d, %Y')}",
            f"{len(group)} shots · best frame selected",
            group,
        )
        for index, group in enumerate(groups[:50])
    ]
    return SmartAlbumsResponse(items=albums, total=len(albums))


@router.get("/people", response_model=SmartAlbumsResponse)
async def people_albums(user: CurrentUser, db: Database) -> SmartAlbumsResponse:
    face_rows = (
        await db.execute(
            select(DetectedFace.id, DetectedFace.image_id, DetectedFace.embedding).where(
                DetectedFace.user_id == user.id
            )
        )
    ).all()
    groups = cluster_faces(
        [(face_id, image_id, list(embedding)) for face_id, image_id, embedding in face_rows],
        settings.face_cluster_threshold,
    )
    all_ids = {image_id for group in groups for image_id in group}
    image_map = {
        image.id: image
        for image in (
            (
                await db.scalars(
                    select(Image).where(
                        Image.user_id == user.id,
                        Image.id.in_(all_ids),
                        or_(
                            Image.status == ProcessingStatus.READY,
                            Image.status == ProcessingStatus.EXACT_DUPLICATE,
                        ),
                    )
                )
            ).all()
            if all_ids
            else []
        )
    }
    albums: list[SmartAlbum] = []
    for index, group in enumerate(groups[:100], start=1):
        images = [image_map[image_id] for image_id in group if image_id in image_map]
        if not images:
            continue
        images.sort(key=image_time, reverse=True)
        albums.append(
            album_payload(
                f"person-{index}",
                f"Person {index}",
                f"{len(images)} photo{'s' if len(images) != 1 else ''}",
                images,
            )
        )
    return SmartAlbumsResponse(items=albums, total=len(albums))
