from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from PIL import Image as PillowImage
from sqlalchemy import select

import app.api.images as image_routes
import app.services.images as image_service
from app.models import Image, JobStatus, ProcessingJob, ProcessingStatus
from tests.conftest import create_user


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, _: str) -> None:
        self.objects[key] = data

    def delete(self, key: str | None) -> None:
        if key:
            self.objects.pop(key, None)

    def presigned_get(self, key: str | None) -> str | None:
        return f"http://objects.test/{key}" if key else None


@pytest.mark.asyncio
async def test_quota_rejects_entire_batch_and_cleans_uploaded_objects(client, monkeypatch):
    auth = await create_user(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    data = png_bytes()
    monkeypatch.setattr(image_routes.settings, "max_user_storage_bytes", len(data) + 1)
    response = await client.post("/api/images/upload", headers=headers, files=[
        ("files", ("first.png", data, "image/png")),
        ("files", ("second.png", data, "image/png")),
    ])
    assert response.status_code == 413
    assert fake.objects == {}
    assert (await client.get("/api/images", headers=headers)).json()["total"] == 0
    accepted = await client.post("/api/images/upload", headers=headers, files=[("files", ("first.png", data, "image/png"))])
    assert accepted.status_code == 202
    exceeded = await client.post("/api/images/upload", headers=headers, files=[("files", ("second.png", data, "image/png"))])
    assert exceeded.status_code == 413
    assert len(fake.objects) == 1


def png_bytes(color: tuple[int, int, int] = (80, 180, 120)) -> bytes:
    output = BytesIO()
    PillowImage.new("RGB", (32, 24), color).save(output, format="PNG")
    return output.getvalue()


def gif_bytes() -> bytes:
    output = BytesIO()
    frames = [PillowImage.new("RGB", (24, 24), color) for color in ("red", "blue")]
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=80)
    return output.getvalue()


@pytest.mark.asyncio
async def test_upload_and_exact_duplicate_detection(client, monkeypatch):
    auth = await create_user(client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    data = png_bytes()

    first = await client.post(
        "/api/images/upload",
        files=[("files", ("garden.png", data, "image/png"))],
        headers=headers,
    )
    assert first.status_code == 202
    assert first.json()["items"][0]["exact_duplicate"] is False

    second = await client.post(
        "/api/images/upload",
        files=[("files", ("garden-copy.png", data, "image/png"))],
        headers=headers,
    )
    assert second.status_code == 202
    item = second.json()["items"][0]
    assert item["exact_duplicate"] is True
    assert item["matched_filename"] == "garden.png"

    gallery = await client.get("/api/images?filter_by=exact", headers=headers)
    assert gallery.status_code == 200
    assert gallery.json()["total"] == 1


@pytest.mark.asyncio
async def test_one_batch_is_grouped_for_immediate_duplicate_review(client, monkeypatch):
    auth = await create_user(client, "batch@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    data = png_bytes()

    upload = await client.post(
        "/api/images/upload",
        files=[
            ("files", ("keeper.png", data, "image/png")),
            ("files", ("copy.png", data, "image/png")),
        ],
        headers=headers,
    )
    assert upload.status_code == 202
    payload = upload.json()
    assert payload["items"][0]["image"]["batch_id"] == payload["batch_id"]
    assert payload["items"][1]["image"]["batch_id"] == payload["batch_id"]

    review = await client.get(
        f"/api/duplicates/review?batch_id={payload['batch_id']}",
        headers=headers,
    )
    assert review.status_code == 200
    report = review.json()
    assert report["total_images_scanned"] == 2
    assert report["total_groups"] == 1
    assert report["exact_duplicates"] == 1
    assert report["groups"][0]["all_same_batch"] is True


@pytest.mark.asyncio
async def test_reindex_route_queues_existing_ready_images(
    client,
    session_factory,
    monkeypatch,
):
    auth = await create_user(client, "reindex@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    queued: list[str] = []
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(
        image_routes,
        "process_image",
        SimpleNamespace(delay=lambda image_id: queued.append(image_id)),
    )
    upload = await client.post(
        "/api/images/upload",
        files=[("files", ("archive.png", png_bytes(), "image/png"))],
        headers=headers,
    )
    image_id = upload.json()["items"][0]["image"]["id"]
    queued.clear()
    async with session_factory() as session:
        image = await session.get(Image, UUID(image_id))
        assert image is not None
        image.status = ProcessingStatus.READY
        job = await session.scalar(select(ProcessingJob).where(ProcessingJob.image_id == image.id))
        job.status = JobStatus.COMPLETE
        await session.commit()

    response = await client.post("/api/images/reindex", headers=headers)
    assert response.status_code == 202
    assert response.json()["queued"] == 1
    assert queued == [image_id]


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_image(client, monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    first_user = await create_user(client, "first@example.com")
    first_headers = {"Authorization": f"Bearer {first_user['access_token']}"}
    upload = await client.post(
        "/api/images/upload",
        files=[("files", ("private.png", png_bytes(), "image/png"))],
        headers=first_headers,
    )
    image_id = upload.json()["items"][0]["image"]["id"]
    second_user = await create_user(client, "second@example.com")
    second_headers = {"Authorization": f"Bearer {second_user['access_token']}"}
    response = await client.get(f"/api/images/{image_id}", headers=second_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_file_is_rejected(client):
    auth = await create_user(client)
    response = await client.post(
        "/api/images/upload",
        files=[("files", ("not-an-image.png", b"not an image", "image/png"))],
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_declared_mime_must_match_decoded_content(client):
    auth = await create_user(client)
    response = await client.post(
        "/api/images/upload",
        files=[("files", ("mismatch.jpg", png_bytes(), "image/jpeg"))],
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_animated_image_and_video_containers_are_accepted(client, monkeypatch):
    auth = await create_user(client, "media@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"

    response = await client.post(
        "/api/images/upload",
        files=[
            ("files", ("motion.gif", gif_bytes(), "image/gif")),
            ("files", ("clip.mp4", mp4, "video/mp4")),
        ],
        headers=headers,
    )

    assert response.status_code == 202
    kinds = [item["image"]["media_kind"] for item in response.json()["items"]]
    assert kinds == ["ANIMATED_IMAGE", "VIDEO"]


@pytest.mark.asyncio
async def test_bulk_delete_removes_multiple_owned_images(client, monkeypatch):
    auth = await create_user(client, "bulk@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    upload = await client.post(
        "/api/images/upload",
        files=[
            ("files", ("first.png", png_bytes((20, 30, 40)), "image/png")),
            ("files", ("second.png", png_bytes((80, 90, 100)), "image/png")),
        ],
        headers=headers,
    )
    image_ids = [item["image"]["id"] for item in upload.json()["items"]]

    response = await client.post(
        "/api/images/bulk-delete",
        json={"image_ids": image_ids, "confirm": True},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 2
    assert fake.objects == {}
    assert (await client.get("/api/images", headers=headers)).json()["total"] == 0


@pytest.mark.asyncio
async def test_bulk_delete_rejects_partial_or_unowned_sets(client, monkeypatch):
    auth = await create_user(client, "atomic@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    fake = FakeStorage()
    monkeypatch.setattr(image_routes, "storage", fake)
    monkeypatch.setattr(image_service, "storage", fake)
    monkeypatch.setattr(image_routes, "process_image", SimpleNamespace(delay=lambda _: None))
    upload = await client.post(
        "/api/images/upload",
        files=[("files", ("keep.png", png_bytes(), "image/png"))],
        headers=headers,
    )
    image_id = upload.json()["items"][0]["image"]["id"]

    response = await client.post(
        "/api/images/bulk-delete",
        json={"image_ids": [image_id, str(uuid4())], "confirm": True},
        headers=headers,
    )
    assert response.status_code == 404
    assert (await client.get("/api/images", headers=headers)).json()["total"] == 1
