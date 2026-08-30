from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image as PillowImage

import app.api.images as image_routes
import app.services.images as image_service
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


def png_bytes(color: tuple[int, int, int] = (80, 180, 120)) -> bytes:
    output = BytesIO()
    PillowImage.new("RGB", (32, 24), color).save(output, format="PNG")
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
