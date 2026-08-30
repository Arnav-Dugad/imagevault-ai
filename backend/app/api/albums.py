from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc, or_, select

from app.api.dependencies import CurrentUser, Database
from app.core.config import get_settings
from app.models import (
    ActivityLog,
    DetectedFace,
    DuplicateMatch,
    DuplicateType,
    FaceAssignment,
    FaceFeedback,
    FaceFeedbackType,
    Image,
    Person,
    ProcessingStatus,
)
from app.schemas import (
    MessageResponse,
    PersonFeedbackRequest,
    PersonIgnoreRequest,
    PersonMergeRequest,
    PersonRenameRequest,
    PersonSplitRequest,
    SmartAlbum,
    SmartAlbumsResponse,
)
from app.services.albums import (
    best_photo,
    group_bursts,
    group_events,
    image_time,
)
from app.services.images import image_summary
from app.services.people import reconcile_people
from app.services.similarity import cosine_similarity

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
async def people_albums(
    user: CurrentUser,
    db: Database,
    include_ignored: bool = False,
) -> SmartAlbumsResponse:
    clusters, _ = await reconcile_people(
        user.id,
        db,
        embedding_model=settings.face_embedding_model,
        base_threshold=settings.face_cluster_threshold,
    )
    visible_clusters = [
        cluster for cluster in clusters if include_ignored or not cluster.person.ignored
    ]
    all_ids = {face[1] for cluster in visible_clusters for face in cluster.faces}
    all_face_ids = {face[0] for cluster in visible_clusters for face in cluster.faces}
    face_rows = (
        await db.execute(
            select(DetectedFace.id, DetectedFace.bounding_box).where(
                DetectedFace.id.in_(all_face_ids)
            )
        )
    ).all() if all_face_ids else []
    face_boxes = dict(face_rows)
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
    for cluster in visible_clusters[:100]:
        group = cluster.faces
        image_ids = list(dict.fromkeys(face[1] for face in group))
        images = [image_map[image_id] for image_id in image_ids if image_id in image_map]
        if len(images) < 2 and not cluster.person.confirmed:
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
                f"person-{cluster.person.id}",
                cluster.person.display_name or f"Person {index}",
                f"{len(images)} photo{'s' if len(images) != 1 else ''}",
                images,
                cover_focus=focus,
            ).model_copy(
                update={
                    "person_id": cluster.person.id,
                    "ignored": cluster.person.ignored,
                    "confirmed": cluster.person.confirmed,
                }
            )
        )
    return SmartAlbumsResponse(items=albums, total=len(albums))


async def _owned_people(person_ids: list[UUID], user_id: UUID, db: Database) -> list[Person]:
    unique_ids = list(dict.fromkeys(person_ids))
    people = list(
        (
            await db.scalars(
                select(Person).where(Person.user_id == user_id, Person.id.in_(unique_ids))
            )
        ).all()
    )
    if len(people) != len(unique_ids):
        raise HTTPException(status_code=404, detail="One or more people were not found")
    people_by_id = {person.id: person for person in people}
    return [people_by_id[person_id] for person_id in unique_ids]


async def _merge_people(
    people: list[Person],
    user_id: UUID,
    db: Database,
    display_name: str | None = None,
) -> Person:
    target = people[0]
    target.confirmed = True
    target.ignored = all(person.ignored for person in people)
    if display_name:
        target.display_name = display_name.strip()
    elif not target.display_name:
        target.display_name = next((person.display_name for person in people if person.display_name), None)
    source_ids = [person.id for person in people[1:]]
    if source_ids:
        assignments = list(
            (
                await db.scalars(
                    select(FaceAssignment).where(
                        FaceAssignment.user_id == user_id,
                        FaceAssignment.person_id.in_(source_ids),
                    )
                )
            ).all()
        )
        for assignment in assignments:
            assignment.person_id = target.id
            assignment.source = "manual"
            assignment.confidence = 1.0
        await db.flush()
        for person in people[1:]:
            await db.delete(person)
    for assignment in (
        await db.scalars(
            select(FaceAssignment).where(FaceAssignment.person_id == target.id)
        )
    ).all():
        assignment.source = "manual"
    return target


@router.post("/people/{person_id}/rename", response_model=MessageResponse)
async def rename_person(
    person_id: UUID,
    request: PersonRenameRequest,
    user: CurrentUser,
    db: Database,
) -> MessageResponse:
    person = (await _owned_people([person_id], user.id, db))[0]
    person.display_name = request.display_name.strip()
    person.confirmed = True
    db.add(ActivityLog(user_id=user.id, action="person.renamed", details={"person_id": str(person.id)}))
    await db.commit()
    return MessageResponse(message=f"Renamed person to {person.display_name}")


@router.post("/people/merge", response_model=MessageResponse)
async def merge_people(
    request: PersonMergeRequest,
    user: CurrentUser,
    db: Database,
) -> MessageResponse:
    people = await _owned_people(request.person_ids, user.id, db)
    if len(people) < 2:
        raise HTTPException(status_code=400, detail="Choose at least two different people")
    target = await _merge_people(people, user.id, db, request.display_name)
    db.add(
        ActivityLog(
            user_id=user.id,
            action="people.merged",
            details={"target_person_id": str(target.id), "count": len(people)},
        )
    )
    await db.commit()
    return MessageResponse(message=f"Merged {len(people)} people")


@router.post("/people/{person_id}/split", response_model=MessageResponse)
async def split_person(
    person_id: UUID,
    request: PersonSplitRequest,
    user: CurrentUser,
    db: Database,
) -> MessageResponse:
    person = (await _owned_people([person_id], user.id, db))[0]
    assignments = list(
        (
            await db.scalars(
                select(FaceAssignment)
                .join(DetectedFace, DetectedFace.id == FaceAssignment.face_id)
                .where(
                    FaceAssignment.user_id == user.id,
                    FaceAssignment.person_id == person.id,
                    DetectedFace.image_id.in_(request.image_ids),
                )
            )
        ).all()
    )
    all_count = int(
        len(
            (
                await db.scalars(
                    select(FaceAssignment.id).where(FaceAssignment.person_id == person.id)
                )
            ).all()
        )
    )
    if not assignments:
        raise HTTPException(status_code=404, detail="No selected photos belong to this person")
    if len(assignments) >= all_count:
        raise HTTPException(status_code=400, detail="Leave at least one photo in the original person")
    separated = Person(
        user_id=user.id,
        display_name=request.display_name.strip() if request.display_name else None,
        confirmed=True,
    )
    db.add(separated)
    await db.flush()
    person.confirmed = True
    for assignment in assignments:
        assignment.person_id = separated.id
        assignment.source = "manual"
        assignment.confidence = 1.0
    db.add(
        ActivityLog(
            user_id=user.id,
            action="person.split",
            details={"person_id": str(person.id), "new_person_id": str(separated.id), "photos": len(assignments)},
        )
    )
    await db.commit()
    return MessageResponse(message=f"Moved {len(assignments)} photo{'s' if len(assignments) != 1 else ''} to a new person")


@router.post("/people/{person_id}/ignore", response_model=MessageResponse)
async def ignore_person(
    person_id: UUID,
    request: PersonIgnoreRequest,
    user: CurrentUser,
    db: Database,
) -> MessageResponse:
    person = (await _owned_people([person_id], user.id, db))[0]
    person.ignored = request.ignored
    person.confirmed = True
    await db.commit()
    return MessageResponse(message="Person hidden" if request.ignored else "Person restored")


@router.post("/people/feedback", response_model=MessageResponse)
async def person_feedback(
    request: PersonFeedbackRequest,
    user: CurrentUser,
    db: Database,
) -> MessageResponse:
    if request.first_person_id == request.second_person_id:
        raise HTTPException(status_code=400, detail="Choose two different people")
    people = await _owned_people(
        [request.first_person_id, request.second_person_id], user.id, db
    )
    representatives: list[tuple[FaceAssignment, DetectedFace]] = []
    for person in people:
        row = (
            await db.execute(
                select(FaceAssignment, DetectedFace)
                .join(DetectedFace, DetectedFace.id == FaceAssignment.face_id)
                .where(FaceAssignment.person_id == person.id)
                .order_by(FaceAssignment.confidence.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=400, detail="A selected person has no face samples")
        representatives.append(row)
    first_face, second_face = representatives[0][1], representatives[1][1]
    ordered = sorted((first_face.id, second_face.id), key=str)
    existing = await db.scalar(
        select(FaceFeedback).where(
            FaceFeedback.first_face_id == ordered[0],
            FaceFeedback.second_face_id == ordered[1],
        )
    )
    similarity = cosine_similarity(list(first_face.embedding), list(second_face.embedding))
    if existing:
        existing.feedback_type = request.feedback_type
        existing.similarity_score = similarity
    else:
        db.add(
            FaceFeedback(
                user_id=user.id,
                first_face_id=ordered[0],
                second_face_id=ordered[1],
                feedback_type=request.feedback_type,
                similarity_score=similarity,
            )
        )
    if request.feedback_type == FaceFeedbackType.SAME:
        await _merge_people(people, user.id, db)
        message = "Saved as the same person and merged their albums"
    else:
        for person in people:
            person.confirmed = True
        message = "Saved as different people; future clustering will respect this"
    db.add(
        ActivityLog(
            user_id=user.id,
            action="person.feedback",
            details={"type": request.feedback_type.value, "similarity": round(similarity, 4)},
        )
    )
    await db.commit()
    return MessageResponse(message=message)
