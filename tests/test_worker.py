"""The laptop AI worker and the website share the work without analysing a photo twice."""

import io

from PIL import Image
from sqlalchemy import text

from app import intelligence
from app.database import connect
from app.worker import load_env_file


def upload(client, color: str) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buffer, "PNG")
    return client.post("/api/photos", files={"file": (f"{color}.png", buffer.getvalue())}).json()["photo"]["id"]


def test_website_leaves_new_photos_to_an_online_laptop(client):
    photo = upload(client, "red")
    intelligence.heartbeat("laptop:test", "laptop")
    assert client.get("/api/ai").json()["runs_on"] == "laptop"

    assert intelligence._claim_next("cloud:site", "cloud") is None    # the website waits for the laptop...
    assert intelligence._claim_next("laptop:test", "laptop") == photo  # ...which takes the photo


def test_website_takes_over_when_photos_wait_too_long(client):
    photo = upload(client, "blue")
    intelligence.heartbeat("laptop:test", "laptop")
    with connect() as conn:
        conn.execute(text("UPDATE photos SET uploaded_at = :old"), {"old": intelligence._ago(3600)})
    assert intelligence._claim_next("cloud:site", "cloud") == photo


def test_website_works_alone_when_no_laptop_is_online(client):
    photo = upload(client, "green")
    assert client.get("/api/ai").json()["runs_on"] == "cloud"
    assert intelligence._claim_next("cloud:site", "cloud") == photo


def test_photos_claimed_by_a_silent_worker_are_retried(client):
    photo = upload(client, "white")
    assert intelligence._claim_next("laptop:gone", "laptop") == photo
    intelligence._release_stale_claims()  # the laptop never sent a heartbeat
    with connect() as conn:
        assert conn.execute(text("SELECT ai_status FROM photos")).scalar_one() is None


def test_worker_env_file_from_powershell_or_bash(tmp_path, monkeypatch):
    for encoding in ("utf-16", "utf-8"):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        path = tmp_path / f"worker-{encoding}.env"
        path.write_text('DATABASE_URL="postgresql+psycopg://u:p@db:5432/x"\n# comment\n', encoding=encoding)
        load_env_file(path)
        import os
        assert os.environ["DATABASE_URL"] == "postgresql+psycopg://u:p@db:5432/x"
