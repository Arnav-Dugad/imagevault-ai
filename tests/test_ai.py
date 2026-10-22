"""Tests for the free AI features, using real public-domain photos (see assets/CREDITS.md)."""

import io
from pathlib import Path

import pytest
from PIL import Image, ImageEnhance, ImageOps

from app import intelligence

ASSETS = Path(__file__).parent / "assets"
pytestmark = pytest.mark.usefixtures("ai_models")  # downloads the models once (about 190 MB)


def upload(client, name: str, data: bytes | None = None) -> str:
    data = data or (ASSETS / name).read_bytes()
    return client.post("/api/photos", files={"file": (name, data)}).json()["photo"]["id"]


def test_same_person_is_recognised_across_photos(client):
    first = upload(client, "person-a-1.jpg")
    upload(client, "person-a-2.jpg")
    other = upload(client, "person-b.jpg")
    assert intelligence.process_pending() == 3

    people = client.get("/api/people").json()
    assert len(people) == 1 and people[0]["photos"] == 2  # person B is in only one photo, so not listed
    person_id = people[0]["id"]
    assert client.get(people[0]["image_url"]).headers["content-type"] == "image/jpeg"

    in_photo = client.get(f"/api/photos/{first}").json()["people"]
    assert [face["person_id"] for face in in_photo] == [person_id]
    assert client.get(f"/api/photos/{other}").json()["people"][0]["person_id"] != person_id

    client.put(f"/api/people/{person_id}", json={"name": "Person A"})
    details = client.get(f"/api/people/{person_id}").json()
    assert details["name"] == "Person A" and len(details["photos"]) == 2

    # Portraits of different people must not be grouped as "same subject".
    assert client.get("/api/related").json() == []

    client.delete(f"/api/photos/{first}")
    assert client.get("/api/people").json() == []


def test_same_subject_shot_differently_and_smart_search(client):
    landmark = Image.open(ASSETS / "landmark.jpg")
    # A "different shot": mirrored, cropped and with warmer colours, so it is NOT a copy.
    width, height = landmark.size
    other_shot = ImageOps.mirror(landmark).crop((0, int(height * 0.12), int(width * 0.85), height))
    other_shot = ImageEnhance.Color(ImageEnhance.Brightness(other_shot).enhance(1.15)).enhance(1.6)
    buffer = io.BytesIO()
    other_shot.save(buffer, "JPEG", quality=85)

    first = upload(client, "landmark.jpg")
    second = upload(client, "landmark-other-shot.jpg", buffer.getvalue())
    upload(client, "person-a-1.jpg")
    intelligence.process_pending()

    assert client.get("/api/duplicates").json() == []  # not copies...
    related = client.get("/api/related").json()        # ...but the same subject
    assert len(related) == 1
    assert {item["photo"]["id"] for item in related[0]["items"]} == {first, second}

    results = client.get("/api/photos?smart=true&search=eiffel tower").json()["items"]
    assert {photo["id"] for photo in results} == {first, second}
    results = client.get("/api/photos?smart=true&search=a man in a suit").json()["items"]
    assert [photo["filename"] for photo in results] == ["person-a-1.jpg"]
    # Something that is in none of the photos gives no results, rather than random photos.
    assert client.get("/api/photos?smart=true&search=a red sports car").json()["items"] == []


def test_ai_status_and_cloud_card(client):
    upload(client, "landmark.jpg")
    assert client.get("/api/ai").json()["waiting"] == 1
    intelligence.process_pending()
    status = client.get("/api/ai").json()
    assert status["ready"] and status["analysed"] == 1 and status["waiting"] == 0
    card = next(s for s in client.get("/api/system").json()["services"] if s["id"] == "ai")
    assert card["healthy"] and "1 photos analysed" in card["detail"]
