from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import desc, or_, select

from app.api.dependencies import CurrentUser, Database
from app.core.config import get_settings
from app.models import DetectedFace, DuplicateMatch, DuplicateType, Image, ProcessingStatus
from app.schemas import SmartAlbum, SmartAlbumsResponse
from app.services.albums import (
    best_photo,
    cluster_face_records,
    group_bursts,
    group_events,
    image_time,
)
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
    *,
    cover_focus: tuple[float, float] | None = None,
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
        cover_focus_x=cover_focus[0] if cover_focus else None,
        cover_focus_y=cover_focus[1] if cover_focus else None,
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
            select(
                DetectedFace.id,
                DetectedFace.image_id,
                DetectedFace.embedding,
                DetectedFace.confidence,
                DetectedFace.bounding_box,
            ).where(
                DetectedFace.user_id == user.id,
                DetectedFace.embedding_model == settings.face_embedding_model,
                DetectedFace.confidence >= 0.45,
            )
        )
    ).all()
    groups = cluster_face_records(
        [
            (face_id, image_id, list(embedding), confidence)
            for face_id, image_id, embedding, confidence, _ in face_rows
        ],
        settings.face_cluster_threshold,
    )
    all_ids = {face[1] for group in groups for face in group}
    face_boxes = {face_id: box for face_id, _, _, _, box in face_rows}
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
    for group in groups[:100]:
        image_ids = list(dict.fromkeys(face[1] for face in group))
        images = [image_map[image_id] for image_id in image_ids if image_id in image_map]
        # A single sighting is not yet a useful people album. Suppressing
        # singletons also avoids a wall of misleading "Person 1" cards while
        # the model gathers enough evidence to form a confident identity.
        if len(images) < 2:
            continue
        images.sort(key=image_time, reverse=True)
        keeper = best_photo(images)
        keeper_face = next((face for face in group if face[1] == keeper.id), None)
        box = face_boxes.get(keeper_face[0]) if keeper_face else None
        focus = None
        if box and keeper.width and keeper.height:
            focus = (
                max(0.0, min(1.0, (box["x"] + box["width"] / 2) / keeper.width)),
                max(0.0, min(1.0, (box["y"] + box["height"] / 2) / keeper.height)),
            )
        index = len(albums) + 1
        albums.append(
            album_payload(
                f"person-{min(str(face[0]) for face in group)}",
                f"Person {index}",
                f"{len(images)} photo{'s' if len(images) != 1 else ''}",
                images,
                cover_focus=focus,
            )
        )
    return SmartAlbumsResponse(items=albums, total=len(albums))
