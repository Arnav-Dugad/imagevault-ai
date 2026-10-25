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


def test_auto_albums(client):
    landmark = upload(client, "landmark.jpg")
    person = upload(client, "person-a-1.jpg")
    intelligence.process_pending()
    albums = {a["id"]: a for a in client.get("/api/albums").json()["auto"]}
    assert landmark in [p["id"] for p in client.get("/api/photos?album=auto:landmarks").json()["items"]]
    assert albums["auto:people"]["count"] == 1
    assert [p["id"] for p in client.get("/api/photos?album=auto:people").json()["items"]] == [person]


def test_burst_keeps_the_sharpest(client):
    from PIL import ImageFilter

    frame = Image.open(ASSETS / "landmark.jpg")

    def shot(second: int, blur: float) -> bytes:
        image = frame.filter(ImageFilter.GaussianBlur(blur)) if blur else frame
        exif = Image.Exif()
        exif[306] = f"2026:10:20 14:03:{second:02d}"
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=90, exif=exif)
        return buffer.getvalue()

    upload(client, "burst-1.jpg", shot(1, 3))
    sharp = upload(client, "burst-2.jpg", shot(2, 0))
    upload(client, "burst-3.jpg", shot(3, 1.5))
    upload(client, "later.jpg", shot(59, 0))  # a minute later: not part of the burst
    upload(client, "later (copy).jpg", shot(59, 0))  # an exact copy is a duplicate, not a burst
    intelligence.process_pending()

    bursts = client.get("/api/bursts").json()
    assert len(bursts) == 1 and len(bursts[0]["items"]) == 3
    assert bursts[0]["sharpest_id"] == sharp == bursts[0]["items"][0]["photo"]["id"]
    in_related = {i["photo"]["id"] for g in client.get("/api/related").json() for i in g["items"]}
    assert sharp not in in_related  # burst shots are not listed again as "same subject"


def test_merge_and_split_people_by_hand(client):
    upload(client, "person-a-1.jpg")
    upload(client, "person-a-2.jpg")
    upload(client, "person-b.jpg")
    upload(client, "person-b.jpg", (ASSETS / "person-b.jpg").read_bytes()[:-1] + b"\xd9")  # a second copy of B
    intelligence.process_pending()
    people = client.get("/api/people").json()
    assert len(people) == 2

    merged = client.post("/api/people/merge", json={"ids": [p["id"] for p in people]}).json()["id"]
    assert [p["photos"] for p in client.get("/api/people").json()] == [4]

    faces = client.get(f"/api/people/{merged}").json()["faces"]
    person_b_faces = [f["id"] for f in faces][:1]
    client.post(f"/api/people/{merged}/split", json={"face_ids": person_b_faces})
    assert sorted(p["photos"] for p in client.get("/api/people").json()) == [1, 3]

    # Analysing photos again must not undo the manual merge and split.
    intelligence.analyze_photo(faces[0]["photo_id"])
    assert sorted(p["photos"] for p in client.get("/api/people").json()) == [1, 3]


def text_photo(words: str) -> bytes:
    image = Image.new("RGB", (900, 400), "white")
    from PIL import ImageDraw, ImageFont
    ImageDraw.Draw(image).text((60, 150), words, fill="black", font=ImageFont.load_default(size=72))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


def test_text_in_photos_is_searchable(client):
    sign = upload(client, "sign.jpg", text_photo("HOTEL PARADISE"))
    upload(client, "landmark.jpg")
    intelligence.process_pending()

    assert "paradise" in client.get(f"/api/photos/{sign}").json()["text"]
    assert [p["id"] for p in client.get("/api/photos?search=paradise").json()["items"]] == [sign]
    assert [p["id"] for p in client.get("/api/photos?search=hotel paradise").json()["items"]] == [sign]


def test_laptop_worker_sends_its_results_over_https(client):
    photo = upload(client, "person-a-1.jpg")
    client.put("/api/ai/mode", json={"mode": "laptop"})

    reply = client.post("/api/worker/next", json={"name": "my-laptop"}).json()
    assert reply["photo"]["id"] == photo
    found = intelligence.compute(client.get(reply["photo"]["file_url"]).content)  # done on the laptop
    assert client.post(f"/api/worker/result/{photo}", json=found.to_json()).json() == {"saved": True}

    details = client.get(f"/api/photos/{photo}").json()
    assert len(details["people"]) == 1
    assert client.get(details["people"][0]["image_url"]).headers["content-type"] == "image/jpeg"
    assert client.get("/api/ai").json()["analysed"] == 1
    assert client.post(f"/api/worker/result/{photo}", json={"clip": "?"}).status_code == 422
