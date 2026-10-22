import io
import os

import pytest
from PIL import Image, ImageDraw


def scene() -> Image.Image:
    image = Image.new("RGB", (512, 384), "#92b6d5")
    draw = ImageDraw.Draw(image)
    draw.polygon([(0, 300), (150, 80), (300, 300)], fill="#324f42")
    draw.rectangle((230, 130, 460, 330), fill="#bc7751")
    for x in range(245, 455, 35):
        for y in range(150, 315, 35):
            draw.rectangle((x, y, x + 18, y + 23), fill="#233142")
    draw.ellipse((350, 30, 420, 100), fill="#f5dd95")
    return image


def document() -> Image.Image:
    image = Image.new("RGB", (512, 384), "white")
    ImageDraw.Draw(image).text((45, 40), "A completely different picture\nwith some text on it", fill="black")
    return image


def encode(image: Image.Image, fmt: str = "PNG", **options) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt, **options)
    return buffer.getvalue()


def upload(client, name: str, data: bytes):
    return client.post("/api/photos", files={"file": (name, data)})


def test_upload_list_and_download(client):
    original = encode(scene())
    response = upload(client, "house.png", original)
    assert response.status_code == 201
    photo = response.json()["photo"]
    assert response.json()["match"] is None
    assert (photo["width"], photo["height"], photo["filename"]) == (512, 384, "house.png")

    listing = client.get("/api/photos").json()
    assert listing["total"] == 1 and listing["items"][0]["match"] is None
    assert client.get(photo["file_url"]).content == original
    assert client.get(photo["thumb_url"]).headers["content-type"] == "image/jpeg"


def test_exact_copy_is_detected_and_stored_once(client):
    data = encode(scene())
    first = upload(client, "a.png", data).json()["photo"]
    second = upload(client, "copy of a.png", data).json()
    assert second["match"] == {"id": first["id"], "filename": "a.png", "kind": "exact", "similarity": 1.0}

    stats = client.get("/api/stats").json()
    assert stats["photos"] == 2 and stats["exact_copies"] == 1 and stats["saved_bytes"] == len(data)

    # Deleting one copy must keep the shared file for the other one...
    client.delete(f"/api/photos/{second['photo']['id']}")
    assert client.get(first["file_url"]).content == data

    # ...and deleting the last copy removes the file from storage.
    from app.storage import get_storage, original_key

    client.delete(f"/api/photos/{first['id']}")
    with pytest.raises(Exception):
        get_storage().read(original_key(first["sha256"]))


EDITED_COPIES = {
    "resized": lambda: encode(scene().resize((256, 192))),
    "compressed": lambda: encode(scene(), "JPEG", quality=60),
    "brighter": lambda: encode(scene().point(lambda v: min(255, v + 12)), "JPEG", quality=90),
}


@pytest.mark.parametrize("edit", EDITED_COPIES)
def test_similar_copies_are_detected(client, edit):
    upload(client, "original.png", encode(scene()))
    match = upload(client, f"{edit}.jpg", EDITED_COPIES[edit]()).json()["match"]
    assert match["kind"] == "similar" and match["similarity"] > 0.8


def test_different_photos_are_not_matched(client):
    upload(client, "house.png", encode(scene()))
    assert upload(client, "doc.png", encode(document())).json()["match"] is None
    assert upload(client, "portrait.png", encode(scene().resize((200, 400)))).json()["match"] is None
    assert client.get("/api/duplicates").json() == []


def test_duplicate_groups_and_remove_exact(client):
    data = encode(scene())
    upload(client, "small.png", encode(scene().resize((256, 192))))
    big = upload(client, "big.png", data).json()["photo"]
    upload(client, "big copy.png", data)

    groups = client.get("/api/duplicates").json()
    assert len(groups) == 1
    kinds = [item["kind"] for item in groups[0]["items"]]
    assert kinds[0] == "keep" and groups[0]["items"][0]["photo"]["id"] == big["id"]
    assert sorted(kinds[1:]) == ["exact", "similar"]

    assert client.post("/api/duplicates/remove-exact").json() == {"removed": 1}
    assert client.get("/api/photos").json()["total"] == 2
    assert client.get("/api/photos/" + big["id"]).json()["matches"][0]["kind"] == "similar"


def test_bad_uploads_are_rejected(client):
    assert upload(client, "notes.txt", b"hello").status_code == 415
    assert upload(client, "broken.jpg", encode(scene(), "JPEG")[:200]).status_code == 415
    assert client.get("/api/photos/missing").status_code == 404


def test_search_and_duplicates_filter(client):
    upload(client, "Beach Holiday.png", encode(scene()))
    upload(client, "beach copy.png", encode(scene()))
    upload(client, "notes.png", encode(document()))
    assert client.get("/api/photos?search=BEACH").json()["total"] == 2
    assert client.get("/api/photos?duplicates_only=true").json()["total"] == 2


def test_health_and_cloud_status(client):
    assert client.get("/api/health").json()["status"] == "ok"
    status = client.get("/api/system").json()
    services = {s["id"]: s for s in status["services"]}
    assert set(services) == {"app-service", "database", "storage", "monitoring", "ai"}
    assert services["database"]["healthy"] and services["storage"]["healthy"]
    assert services["database"]["active"] == bool(os.environ.get("TEST_DATABASE_URL"))
    assert services["storage"]["active"] == bool(os.environ.get("TEST_AZURE_STORAGE"))


def test_password_protection(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "secret")
    assert client.get("/api/photos").status_code == 401
    assert client.get("/api/session").json() == {"password_required": True, "logged_in": False}
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"password": "secret"}).status_code == 200
    assert client.get("/api/photos").status_code == 200
    assert client.get("/api/health").status_code == 200  # the deploy pipeline needs this without a password
