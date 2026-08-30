from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import (
    DetectedFace,
    FaceAssignment,
    FaceFeedback,
    Image,
    Person,
    ProcessingStatus,
)
from tests.conftest import create_user


def _image(user_id: UUID, name: str) -> Image:
    image_id = uuid4()
    return Image(
        id=image_id,
        user_id=user_id,
        original_filename=name,
        object_key=f"objects/{image_id}.jpg",
        thumbnail_key=f"thumbs/{image_id}.webp",
        mime_type="image/jpeg",
        file_size=1000,
        width=400,
        height=400,
        sha256=uuid4().hex + uuid4().hex,
        status=ProcessingStatus.READY,
        quality_score=0.8,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_people_can_be_renamed_hidden_and_taught_as_different(
    client,
    session_factory,
):
    auth = await create_user(client, "people@example.com")
    user_id = UUID(auth["user"]["id"])
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    settings = get_settings()

    async with session_factory() as session:
        people = [
            Person(user_id=user_id, display_name="First", confirmed=True),
            Person(user_id=user_id, display_name="Second", confirmed=True),
        ]
        session.add_all(people)
        await session.flush()
        for person_index, person in enumerate(people):
            for photo_index in range(2):
                image = _image(user_id, f"person-{person_index}-{photo_index}.jpg")
                session.add(image)
                await session.flush()
                vector = [1.0, 0.01 * photo_index] if person_index == 0 else [0.01, 1.0]
                face = DetectedFace(
                    user_id=user_id,
                    image_id=image.id,
                    face_index=0,
                    bounding_box={"x": 80, "y": 70, "width": 180, "height": 190},
                    embedding=vector,
                    confidence=0.98,
                    embedding_model=settings.face_embedding_model,
                )
                session.add(face)
                await session.flush()
                session.add(
                    FaceAssignment(
                        user_id=user_id,
                        person_id=person.id,
                        face_id=face.id,
                        source="manual",
                        confidence=1.0,
                    )
                )
        await session.commit()

    albums = await client.get("/api/albums/people", headers=headers)
    assert albums.status_code == 200
    items = albums.json()["items"]
    assert {item["title"] for item in items} == {"First", "Second"}
    people_by_title = {item["title"]: item["person_id"] for item in items}

    renamed = await client.post(
        f"/api/albums/people/{people_by_title['First']}/rename",
        json={"display_name": "Family"},
        headers=headers,
    )
    assert renamed.status_code == 200

    feedback = await client.post(
        "/api/albums/people/feedback",
        json={
            "first_person_id": people_by_title["First"],
            "second_person_id": people_by_title["Second"],
            "feedback_type": "DIFFERENT",
        },
        headers=headers,
    )
    assert feedback.status_code == 200
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(FaceFeedback)) == 1

    duplicate_merge = await client.post(
        "/api/albums/people/merge",
        json={"person_ids": [people_by_title["First"], people_by_title["First"]]},
        headers=headers,
    )
    assert duplicate_merge.status_code == 400

    hidden = await client.post(
        f"/api/albums/people/{people_by_title['First']}/ignore",
        json={"ignored": True},
        headers=headers,
    )
    assert hidden.status_code == 200
    assert (await client.get("/api/albums/people", headers=headers)).json()["total"] == 1
    visible = await client.get("/api/albums/people?include_ignored=true", headers=headers)
    assert visible.json()["total"] == 2
    assert any(item["ignored"] for item in visible.json()["items"])
