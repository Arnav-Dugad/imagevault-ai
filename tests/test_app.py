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
    assert client.get("/api/photos?filter=duplicates").json()["total"] == 2


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


def test_guessing_the_password_is_blocked(client, monkeypatch):
    from app import server

    monkeypatch.setenv("APP_PASSWORD", "8574")
    server._failed_logins.clear()
    for guess in ("0000", "0001", "0002", "0003", "0004"):
        assert client.post("/api/login", json={"password": guess}).status_code == 401
    # Even the right password is refused for 15 minutes after 5 wrong guesses from the same address.
    blocked = client.post("/api/login", json={"password": "8574"})
    assert blocked.status_code == 429 and "Try again in 15 minutes" in blocked.json()["detail"]
    server._failed_logins.clear()
    assert client.post("/api/login", json={"password": "8574"}).status_code == 200


def test_cost_card(client, monkeypatch):
    from app import costs

    monkeypatch.delenv("AZURE_COST_SCOPE", raising=False)
    assert client.get("/api/costs").json()["configured"] is False  # running locally: nothing to report

    calls = []

    def fake_query(scope):
        calls.append(scope)
        return {"amount": 0.12, "currency": "USD", "services": [{"name": "Storage", "amount": 0.12}]}

    costs._cache.clear()
    monkeypatch.setattr(costs, "_query", fake_query)
    monkeypatch.setenv("AZURE_COST_SCOPE", "/subscriptions/x/resourceGroups/imagevault-rg")
    monkeypatch.setenv("MONTHLY_BUDGET", "5")
    report = client.get("/api/costs").json()
    assert report["amount"] == 0.12 and report["budget"] == 5 and report["error"] is None
    assert report["inr_rate"] > 1  # the website shows rupees; Azure for Students bills in US dollars
    client.get("/api/costs")
    assert len(calls) == 1  # cached for an hour, so Azure's API is not called on every page view


def photo_taken(when: str, color: str = "red", **save) -> bytes:
    image = Image.new("RGB", (64, 48), color)
    exif = Image.Exif()
    exif[306] = when  # the camera's date, as phones write it
    return encode(image, "JPEG", exif=exif, **save)


def test_camera_date_filters_and_sorting(client):
    old = upload(client, "old.jpg", photo_taken("2024:01:05 10:00:00", "red")).json()["photo"]
    new = upload(client, "new.jpg", photo_taken("2026:03:01 09:30:00", "blue")).json()["photo"]
    big = upload(client, "big.png", encode(scene())).json()["photo"]  # no camera date: uses the upload date
    assert old["taken_at"] == "2024-01-05T10:00:00"

    def names(query):
        return [p["filename"] for p in client.get(f"/api/photos?{query}").json()["items"]]

    assert names("date_from=2024-01-01&date_to=2024-12-31") == ["old.jpg"]
    assert names("sort=taken_old")[:2] == ["old.jpg", "new.jpg"]
    assert names("sort=largest")[0] == "big.png"
    assert names("sort=name") == ["big.png", "new.jpg", "old.jpg"]
    assert {new["id"], big["id"]} <= {p["id"] for p in client.get("/api/photos?date_from=2026-01-01").json()["items"]}


def test_batch_favourite_album_download_and_delete(client):
    ids = [upload(client, f"{c}.jpg", photo_taken("2026:01:01 00:00:00", c)).json()["photo"]["id"]
           for c in ("red", "green", "blue")]

    assert client.post("/api/photos/batch", json={"ids": ids[:2], "action": "favorite"}).json() == {"done": 2}
    assert client.get("/api/photos?filter=favorites").json()["total"] == 2

    added = client.post("/api/photos/batch", json={"ids": ids, "action": "add_to_album", "new_album": "Trip"})
    assert added.json() == {"done": 3}
    album = client.get("/api/albums").json()["mine"][0]
    assert album["name"] == "Trip" and album["count"] == 3
    client.post("/api/photos/batch", json={"ids": ids[:1], "action": "remove_from_album", "album_id": album["id"]})
    assert client.get(f"/api/photos?album={album['id']}").json()["total"] == 2

    renamed = client.patch(f"/api/photos/{ids[0]}", json={"filename": "holiday.jpg", "favorite": False}).json()
    assert renamed["filename"] == "holiday.jpg" and not renamed["favorite"]

    archive = client.get(f"/api/zip?ids={','.join(ids)}")
    assert archive.headers["content-type"] == "application/zip"
    import zipfile
    assert sorted(zipfile.ZipFile(io.BytesIO(archive.content)).namelist()) == ["blue.jpg", "green.jpg", "holiday.jpg"]

    assert client.post("/api/photos/batch", json={"ids": ids, "action": "delete"}).json() == {"done": 3}
    assert client.get("/api/photos").json()["total"] == 0
    assert client.get("/api/albums").json()["mine"][0]["count"] == 0  # the album stays, now empty


def test_sharpest_photo_in_a_group(client):
    from PIL import ImageFilter

    sharp = upload(client, "sharp.png", encode(scene())).json()["photo"]
    upload(client, "blurry.png", encode(scene().filter(ImageFilter.GaussianBlur(2))))
    group = client.get("/api/duplicates").json()[0]
    assert group["sharpest_id"] == sharp["id"]


def test_storage_usage_space_saved_and_delete_everything(client):
    original = encode(scene())
    first = upload(client, "scene.png", original).json()["photo"]
    copy = upload(client, "scene (copy).png", original).json()["photo"]
    upload(client, "document.png", encode(document()))

    usage = client.get("/api/storage").json()
    parts = {p["key"]: p["bytes"] for p in usage["parts"]}
    assert parts["originals"] == first["size"] + len(encode(document()))  # the copy is stored once
    assert parts["thumbnails"] > 0 and usage["total_bytes"] == sum(parts.values())
    assert usage["saved_bytes"] == copy["size"] and usage["monthly_cost"] >= 0
    assert usage["inr_rate"] > 1

    client.delete(f"/api/photos/{copy['id']}?duplicate=true")  # removed on the Duplicates page
    assert client.get("/api/storage").json()["saved_bytes"] == copy["size"]  # still counted as saved

    album = client.post("/api/photos/batch", json={"ids": [first["id"]], "action": "add_to_album", "new_album": "A"})
    assert album.status_code == 200
    assert client.get("/api/albums").json()["mine"][0]["bytes"] == first["size"]

    assert client.post("/api/reset", json={"confirm": "yes"}).status_code == 422
    assert client.post("/api/reset", json={"confirm": "delete everything"}).json() == {"ok": True}
    assert client.get("/api/photos").json()["total"] == 0
    assert client.get("/api/albums").json()["mine"] == []
    after = client.get("/api/storage").json()
    assert after["total_bytes"] == 0 and after["saved_bytes"] == 0
