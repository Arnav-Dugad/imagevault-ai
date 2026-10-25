"""The ImageVault web server: a JSON API plus the website itself."""

import hashlib
import hmac
import json
import logging
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import MAX_UPLOAD_BYTES, database_url, env

# Application Insights must be set up before FastAPI is imported, so requests are tracked automatically.
if env("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(logger_name="imagevault")

from fastapi import FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from sqlalchemy import bindparam, make_url, text  # noqa: E402

from app import __version__, ai, costs, intelligence  # noqa: E402
from app.database import connect, init_db  # noqa: E402
from app.photos import NotAPhoto, analyze, compare  # noqa: E402
from app.storage import get_storage, original_key, thumbnail_key  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
SESSION_COOKIE = "imagevault_session"

log = logging.getLogger("imagevault")
log.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    intelligence.start_worker()  # analyses photos with AI in the background
    yield


app = FastAPI(title="ImageVault", version=__version__, lifespan=lifespan)
init_db()


# --- Optional password (only used when APP_PASSWORD is set) -----------------

def _session_token(password: str) -> str:
    return hmac.new(password.encode(), b"imagevault-session", hashlib.sha256).hexdigest()


def _logged_in(request: Request) -> bool:
    password = env("APP_PASSWORD")
    if not password:
        return True
    return hmac.compare_digest(request.cookies.get(SESSION_COOKIE, ""), _session_token(password))


@app.middleware("http")
async def require_password(request: Request, call_next):
    path = request.url.path
    public = path in ("/api/session", "/api/login", "/api/health") or not path.startswith("/api/")
    if not public and not _logged_in(request):
        return JSONResponse({"detail": "Please log in."}, status_code=401)
    return await call_next(request)


class Login(BaseModel):
    password: str


@app.get("/api/session")
def session(request: Request):
    return {"password_required": bool(env("APP_PASSWORD")), "logged_in": _logged_in(request)}


MAX_FAILED_LOGINS = 5          # wrong passwords allowed per address...
LOCKOUT_SECONDS = 15 * 60      # ...within this time, before that address is blocked
_failed_logins: dict[str, list[float]] = {}
_failed_lock = threading.Lock()


def _recent_failures(address: str) -> list[float]:
    cutoff = time.monotonic() - LOCKOUT_SECONDS
    with _failed_lock:
        attempts = [t for t in _failed_logins.get(address, []) if t > cutoff]
        _failed_logins[address] = attempts
        return attempts


@app.post("/api/login")
def login(body: Login, request: Request):
    password = env("APP_PASSWORD")
    address = request.client.host if request.client else "unknown"
    failures = _recent_failures(address)
    if len(failures) >= MAX_FAILED_LOGINS:  # stops scripts from guessing the password
        minutes = max(1, round((failures[0] + LOCKOUT_SECONDS - time.monotonic()) / 60))
        raise HTTPException(429, f"Too many wrong passwords. Try again in {minutes} minutes.")
    if password and not hmac.compare_digest(body.password, password):
        with _failed_lock:
            _failed_logins.setdefault(address, []).append(time.monotonic())
        log.warning("Failed login attempt")
        left = MAX_FAILED_LOGINS - len(failures) - 1
        raise HTTPException(401, f"Wrong password. {left} {'try' if left == 1 else 'tries'} left." if left
                            else "Wrong password. Too many tries: wait 15 minutes.")
    with _failed_lock:
        _failed_logins.pop(address, None)
    response = JSONResponse({"ok": True})
    if password:
        response.set_cookie(
            SESSION_COOKIE, _session_token(password), httponly=True, samesite="lax",
            secure=request.url.scheme == "https", max_age=30 * 24 * 3600,
        )
    return response


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


# --- Photos ------------------------------------------------------------------

def _photo_json(row) -> dict:
    photo = dict(row)
    for hidden in ("phash", "dhash", "clip"):
        photo.pop(hidden, None)
    photo["thumb_url"] = f"/api/photos/{photo['id']}/thumb"
    photo["file_url"] = f"/api/photos/{photo['id']}/file"
    return photo


def _get_photo(conn, photo_id: str):
    row = conn.execute(text("SELECT * FROM photos WHERE id = :id"), {"id": photo_id}).mappings().first()
    if row is None:
        raise HTTPException(404, "Photo not found.")
    return row


COPIES = "kind IN ('exact', 'similar')"  # matches that are copies (not just the same subject)

# Adds a "match" column ('exact', 'similar' or NULL) so the gallery can show a badge.
PHOTO_COLUMNS = f"""
    photos.*,
    (SELECT CASE WHEN COUNT(*) = 0 THEN NULL
                 WHEN SUM(CASE WHEN kind = 'exact' THEN 1 ELSE 0 END) > 0 THEN 'exact'
                 ELSE 'similar' END
       FROM matches WHERE (photo_a = photos.id OR photo_b = photos.id) AND {COPIES}) AS match_kind
"""


def _with_match(row) -> dict:
    photo = _photo_json(row)
    photo["match"] = photo.pop("match_kind", None)
    return photo


def _photos_by_id(conn, ids: list[str]) -> list[dict]:
    """Photos with the given IDs, in the same order."""
    if not ids:
        return []
    rows = conn.execute(
        text(f"SELECT {PHOTO_COLUMNS} FROM photos WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    ).mappings().all()
    by_id = {row["id"]: _with_match(row) for row in rows}
    return [by_id[i] for i in ids if i in by_id]


@app.get("/api/photos")
def list_photos(search: str = "", smart: bool = False, duplicates_only: bool = False,
                offset: int = 0, limit: int = 60):
    limit, offset = max(1, min(limit, 200)), max(0, offset)
    if smart and search.strip():  # AI search: "dog on a beach"
        if not (ai.enabled() and ai.models_ready()):
            raise HTTPException(503, "Smart search is still getting ready. Try again in a minute.")
        ranked = intelligence.search(search.strip())
        with connect() as conn:
            return {"total": len(ranked), "items": _photos_by_id(conn, ranked[offset:offset + limit])}

    where = "WHERE LOWER(filename) LIKE :search"
    if duplicates_only:
        where += (f" AND id IN (SELECT photo_a FROM matches WHERE {COPIES}"
                  f" UNION SELECT photo_b FROM matches WHERE {COPIES})")
    params = {"search": f"%{search.lower()}%", "limit": limit, "offset": offset}
    with connect() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM photos {where}"), params).scalar_one()
        rows = conn.execute(
            text(f"SELECT {PHOTO_COLUMNS} FROM photos {where} ORDER BY uploaded_at DESC LIMIT :limit OFFSET :offset"),
            params,
        ).mappings().all()
    return {"total": total, "items": [_with_match(row) for row in rows]}


@app.post("/api/photos", status_code=201)
def upload_photo(file: UploadFile = File(...)):
    started = time.perf_counter()
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "This photo is larger than 25 MB.")
    try:
        info = analyze(data)
    except NotAPhoto as exc:
        raise HTTPException(415, str(exc)) from exc

    storage = get_storage()
    with connect() as conn:
        already_stored = conn.execute(
            text("SELECT 1 FROM photos WHERE sha256 = :sha LIMIT 1"), {"sha": info.sha256}
        ).first()
        if not already_stored:  # identical photos share one stored file
            try:
                storage.save(original_key(info.sha256), data, info.content_type)
                storage.save(thumbnail_key(info.sha256), info.thumbnail, "image/jpeg")
            except Exception as exc:
                log.exception("Saving to storage failed")
                raise HTTPException(502, f"Could not save the photo to storage: {exc}") from exc

        photo = {
            "id": uuid.uuid4().hex,
            "filename": Path(file.filename or "photo").name[:255],
            "content_type": info.content_type,
            "size": len(data),
            "width": info.width,
            "height": info.height,
            "sha256": info.sha256,
            "phash": info.phash,
            "dhash": info.dhash,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.execute(
            text(f"INSERT INTO photos ({', '.join(photo)}) VALUES ({', '.join(':' + k for k in photo)})"), photo
        )

        # Compare the new photo with every photo already in the vault.
        best = None
        others = conn.execute(
            text("SELECT id, filename, sha256, phash, dhash, width, height FROM photos WHERE id != :id"),
            {"id": photo["id"]},
        ).mappings().all()
        for other in others:
            result = compare(photo, dict(other))
            if result is None:
                continue
            kind, similarity = result
            conn.execute(
                text("INSERT INTO matches (photo_a, photo_b, kind, similarity) VALUES (:a, :b, :kind, :similarity)"),
                {"a": photo["id"], "b": other["id"], "kind": kind, "similarity": similarity},
            )
            if best is None or similarity > best["similarity"]:
                best = {"id": other["id"], "filename": other["filename"], "kind": kind, "similarity": similarity}

    log.info("Photo uploaded", extra={"size": len(data), "match": best["kind"] if best else "none",
                                      "seconds": round(time.perf_counter() - started, 3)})
    intelligence.wake()  # start AI analysis in the background
    return {"photo": _photo_json(photo), "match": best}


@app.get("/api/photos/{photo_id}")
def photo_details(photo_id: str):
    with connect() as conn:
        photo = _get_photo(conn, photo_id)
        found = conn.execute(
            text("""SELECT photos.*, matches.kind, matches.similarity FROM matches
                    JOIN photos ON photos.id = CASE WHEN matches.photo_a = :id THEN matches.photo_b
                                                    ELSE matches.photo_a END
                    WHERE matches.photo_a = :id OR matches.photo_b = :id
                    ORDER BY matches.similarity DESC"""),
            {"id": photo_id},
        ).mappings().all()
        in_photo = conn.execute(
            text("""SELECT faces.id, faces.person_id, people.name, faces.x, faces.y, faces.w, faces.h,
                           (SELECT COUNT(DISTINCT f.photo_id) FROM faces f
                             WHERE f.person_id = faces.person_id) AS photos
                    FROM faces LEFT JOIN people ON people.id = faces.person_id
                    WHERE faces.photo_id = :id ORDER BY faces.x"""),
            {"id": photo_id},
        ).mappings().all()
    result = _photo_json(photo)
    result["matches"] = [{"kind": m["kind"], "similarity": m["similarity"], "photo": _photo_json(m)} for m in found]
    result["people"] = [{**dict(face), "image_url": f"/api/faces/{face['id']}/image"} for face in in_photo]
    return result


def _file_response(key: str, content_type: str, headers: dict | None = None) -> Response:
    try:
        data = get_storage().read(key)
    except Exception as exc:
        log.warning("Reading from storage failed: %s", exc)
        raise HTTPException(502, "Could not load this photo from storage.") from exc
    # A photo's content never changes, so browsers may cache it for a long time.
    return Response(data, media_type=content_type,
                    headers={"Cache-Control": "private, max-age=31536000, immutable", **(headers or {})})


@app.get("/api/photos/{photo_id}/thumb")
def photo_thumbnail(photo_id: str):
    with connect() as conn:
        photo = _get_photo(conn, photo_id)
    return _file_response(thumbnail_key(photo["sha256"]), "image/jpeg")


@app.get("/api/photos/{photo_id}/file")
def photo_file(photo_id: str, download: bool = False):
    with connect() as conn:
        photo = _get_photo(conn, photo_id)
    safe_name = re.sub(r'[^\w.\- ]', "_", photo["filename"])
    disposition = "attachment" if download else "inline"
    return _file_response(original_key(photo["sha256"]), photo["content_type"],
                          {"Content-Disposition": f'{disposition}; filename="{safe_name}"'})


def _delete(conn, photo) -> None:
    storage = get_storage()
    face_ids = conn.execute(text("SELECT id FROM faces WHERE photo_id = :id"), {"id": photo["id"]}).scalars().all()
    for face_id in face_ids:
        storage.delete(intelligence.face_key(face_id))
    conn.execute(text("DELETE FROM faces WHERE photo_id = :id"), {"id": photo["id"]})
    conn.execute(text("DELETE FROM people WHERE id NOT IN (SELECT person_id FROM faces WHERE person_id IS NOT NULL)"))
    conn.execute(text("DELETE FROM matches WHERE photo_a = :id OR photo_b = :id"), {"id": photo["id"]})
    conn.execute(text("DELETE FROM photos WHERE id = :id"), {"id": photo["id"]})
    sha = {"sha": photo["sha256"]}
    still_used = conn.execute(text("SELECT 1 FROM photos WHERE sha256 = :sha LIMIT 1"), sha).first()
    if not still_used:  # the last copy is gone, so remove the stored files too
        storage.delete(original_key(photo["sha256"]))
        storage.delete(thumbnail_key(photo["sha256"]))


@app.delete("/api/photos/{photo_id}")
def delete_photo(photo_id: str):
    with connect() as conn:
        _delete(conn, _get_photo(conn, photo_id))
    log.info("Photo deleted")
    return {"ok": True}


# --- Dashboard and duplicate review --------------------------------------------

@app.get("/api/stats")
def stats():
    with connect() as conn:
        total, total_bytes = conn.execute(text("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM photos")).one()
        stored_bytes = conn.execute(text(
            "SELECT COALESCE(SUM(size), 0) FROM (SELECT MAX(size) AS size FROM photos GROUP BY sha256) AS unique_files"
        )).scalar_one()
        unique = conn.execute(text("SELECT COUNT(DISTINCT sha256) FROM photos")).scalar_one()
        similar = conn.execute(text("SELECT COUNT(*) FROM matches WHERE kind = 'similar'")).scalar_one()
        people_count = conn.execute(text(f"SELECT COUNT(*) FROM ({PEOPLE_QUERY}) AS p")).scalar_one()
        recent = conn.execute(
            text(f"SELECT {PHOTO_COLUMNS} FROM photos ORDER BY uploaded_at DESC LIMIT 8")
        ).mappings().all()
    return {
        "photos": total,
        "total_bytes": int(total_bytes),
        "stored_bytes": int(stored_bytes),
        "saved_bytes": int(total_bytes - stored_bytes),
        "exact_copies": total - unique,
        "similar_pairs": similar,
        "people": people_count,
        "storage": get_storage().kind,
        "ai": intelligence.status(),
        "recent": [_with_match(row) for row in recent],
    }


def _matched_groups(kinds: str) -> tuple[list, list[list]]:
    """Photos linked by matches of the given kinds, joined into groups (union-find)."""
    with connect() as conn:
        found = conn.execute(text(f"SELECT * FROM matches WHERE {kinds}")).mappings().all()
        rows = conn.execute(text(
            f"SELECT * FROM photos WHERE id IN (SELECT photo_a FROM matches WHERE {kinds} "
            f"UNION SELECT photo_b FROM matches WHERE {kinds})"
        )).mappings().all()
    photos = {row["id"]: row for row in rows}
    parent = {photo_id: photo_id for photo_id in photos}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in found:
        parent[root(m["photo_a"])] = root(m["photo_b"])
    groups: dict[str, list] = {}
    for photo_id, photo in photos.items():
        groups.setdefault(root(photo_id), []).append(photo)
    return found, list(groups.values())


@app.get("/api/duplicates")
def duplicate_groups():
    """Group photos that are copies of each other. The best copy of each group is listed first."""
    found, groups = _matched_groups(COPIES)
    pair = {frozenset((m["photo_a"], m["photo_b"])): m for m in found}
    best_similarity = {}
    for m in found:
        for photo_id in (m["photo_a"], m["photo_b"]):
            best_similarity[photo_id] = max(best_similarity.get(photo_id, 0), m["similarity"])

    result = []
    for members in groups:
        # Keep the photo with the most pixels, then the largest file (least compressed), then the oldest.
        members.sort(key=lambda p: (-(p["width"] * p["height"]), -p["size"], p["uploaded_at"]))
        keeper = members[0]
        items = []
        seen_files = set()
        for photo in members:
            # Describe every other photo by how it relates to the photo we keep.
            direct = pair.get(frozenset((photo["id"], keeper["id"])))
            if photo is keeper:
                relation = {"kind": "keep", "similarity": 1.0}
            elif photo["sha256"] in seen_files:  # identical to a photo listed before it
                relation = {"kind": "exact", "similarity": 1.0}
            elif direct:
                relation = {"kind": "similar", "similarity": direct["similarity"]}
            else:  # linked to the group through another photo
                relation = {"kind": "similar", "similarity": best_similarity[photo["id"]]}
            seen_files.add(photo["sha256"])
            items.append({**relation, "photo": _photo_json(photo)})
        result.append({"id": keeper["id"], "items": items, "extra_bytes": sum(p["size"] for p in members[1:])})
    result.sort(key=lambda g: max(i["photo"]["uploaded_at"] for i in g["items"]), reverse=True)
    return result


@app.post("/api/duplicates/remove-exact")
def remove_exact_copies():
    """Delete every exact copy, keeping the first upload of each photo."""
    removed = 0
    with connect() as conn:
        rows = conn.execute(text("SELECT * FROM photos ORDER BY uploaded_at")).mappings().all()
        seen = set()
        for photo in rows:
            if photo["sha256"] in seen:
                _delete(conn, photo)
                removed += 1
            seen.add(photo["sha256"])
    log.info("Exact copies removed", extra={"removed": removed})
    return {"removed": removed}


@app.get("/api/related")
def related_groups():
    """Different photos of the same subject or scene, found by AI. These are never deleted automatically."""
    found, groups = _matched_groups("kind = 'subject'")
    best = {}
    for m in found:
        for photo_id in (m["photo_a"], m["photo_b"]):
            best[photo_id] = max(best.get(photo_id, 0), m["similarity"])
    result = []
    for members in groups:
        members.sort(key=lambda p: p["uploaded_at"])
        items = [{"kind": "subject", "similarity": best[p["id"]], "photo": _photo_json(p)} for p in members]
        result.append({"id": members[0]["id"], "items": items, "extra_bytes": 0})
    result.sort(key=lambda g: len(g["items"]), reverse=True)
    return result


# --- People (face recognition) -------------------------------------------------------

# People who appear in at least two different photos; one-off faces are not worth showing.
PEOPLE_QUERY = """
    SELECT people.id, people.name, COUNT(DISTINCT faces.photo_id) AS photos
    FROM people JOIN faces ON faces.person_id = people.id
    GROUP BY people.id, people.name
    HAVING COUNT(DISTINCT faces.photo_id) >= 2
"""


def _cover_faces(conn) -> dict:
    """The largest face of each person, used as their picture."""
    rows = conn.execute(text("SELECT id, person_id, w * h AS area FROM faces WHERE person_id IS NOT NULL")).all()
    cover = {}
    for row in rows:
        if row.person_id not in cover or row.area > cover[row.person_id][1]:
            cover[row.person_id] = (row.id, row.area)
    return {person: f"/api/faces/{face_id}/image" for person, (face_id, _) in cover.items()}


@app.get("/api/people")
def list_people():
    with connect() as conn:
        rows = conn.execute(text(f"{PEOPLE_QUERY} ORDER BY photos DESC, people.name")).mappings().all()
        covers = _cover_faces(conn)
    return [{**dict(row), "image_url": covers.get(row["id"])} for row in rows]


@app.get("/api/people/{person_id}")
def person_details(person_id: str):
    with connect() as conn:
        person = conn.execute(text("SELECT id, name FROM people WHERE id = :id"), {"id": person_id}).mappings().first()
        if person is None:
            raise HTTPException(404, "Person not found.")
        ids = conn.execute(text(
            "SELECT photos.id FROM photos WHERE id IN (SELECT photo_id FROM faces WHERE person_id = :id) "
            "ORDER BY uploaded_at DESC"), {"id": person_id}).scalars().all()
        photos = _photos_by_id(conn, list(ids))
        cover = _cover_faces(conn).get(person_id)
    return {**dict(person), "image_url": cover, "photos": photos}


class PersonName(BaseModel):
    name: str


@app.put("/api/people/{person_id}")
def rename_person(person_id: str, body: PersonName):
    name = body.name.strip()[:100] or None
    with connect() as conn:
        updated = conn.execute(text("UPDATE people SET name = :name WHERE id = :id"),
                               {"name": name, "id": person_id}).rowcount
    if not updated:
        raise HTTPException(404, "Person not found.")
    return {"id": person_id, "name": name}


@app.get("/api/faces/{face_id}/image")
def face_image(face_id: str):
    with connect() as conn:
        if conn.execute(text("SELECT 1 FROM faces WHERE id = :id"), {"id": face_id}).first() is None:
            raise HTTPException(404, "Face not found.")
    return _file_response(intelligence.face_key(face_id), "image/jpeg")


@app.get("/api/ai")
def ai_status():
    return intelligence.status()


@app.get("/api/costs")
def azure_costs():
    """This month's Azure spending for the project (Azure Cost Management), cached for an hour."""
    return costs.month_to_date()


# --- Health and cloud status -------------------------------------------------------

@app.get("/api/health")
def health():
    """Used by the deployment pipeline to check the new version works."""
    with connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}


def _timed(check) -> tuple[bool, int, str | None]:
    started = time.perf_counter()
    try:
        check()
        return True, round((time.perf_counter() - started) * 1000), None
    except Exception as exc:
        return False, round((time.perf_counter() - started) * 1000), str(exc).splitlines()[0][:200]


def _check_database():
    with connect() as conn:
        conn.execute(text("SELECT 1"))


def _build_info() -> dict | None:
    """Written by the GitHub Actions deploy job (see .github/workflows/ci-cd.yml)."""
    try:
        return json.loads((APP_DIR / "build.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@app.get("/api/system")
def system_status():
    """Live status of each cloud service, shown on the Cloud page."""
    site = env("WEBSITE_SITE_NAME")
    db_url = make_url(database_url())
    postgres = db_url.get_backend_name() == "postgresql"
    db_ok, db_ms, db_error = _timed(_check_database)
    storage = get_storage()
    st_ok, st_ms, st_error = _timed(storage.check)
    insights = bool(env("APPLICATIONINSIGHTS_CONNECTION_STRING"))
    brain = intelligence.status()
    where = "on your laptop (edge)" if brain["runs_on"] == "laptop" else "in App Service"
    ai_detail = (f"Running {where} · {brain['analysed']} photos analysed"
                 + (f", {brain['waiting']} waiting" if brain["waiting"] else "")
                 if brain["ready"] else brain["message"])
    return {
        "version": __version__,
        "environment": "Azure" if site else "Local",
        "build": _build_info(),
        "ai_runs_on": brain["runs_on"],
        "services": [
            {"id": "app-service", "name": "Azure App Service", "role": "Hosts the website and API",
             "active": bool(site), "healthy": True, "latency_ms": None,
             "detail": f"{site}.azurewebsites.net" if site else "Running on this computer", "error": None},
            {"id": "database", "name": "Azure Database for PostgreSQL", "role": "Stores photo details and matches",
             "active": postgres, "healthy": db_ok, "latency_ms": db_ms,
             "detail": db_url.host if postgres else "Local SQLite file", "error": db_error},
            {"id": "storage", "name": "Azure Blob Storage", "role": "Stores the photos and thumbnails",
             "active": storage.kind == "azure", "healthy": st_ok, "latency_ms": st_ms,
             "detail": storage.description if storage.kind == "azure" else "Local folder", "error": st_error},
            {"id": "monitoring", "name": "Application Insights", "role": "Tracks requests, errors and logs",
             "active": insights, "healthy": insights, "latency_ms": None,
             "detail": "Sending telemetry" if insights else "Not configured", "error": None},
            {"id": "ai", "name": "Free AI recognition",
             "role": "CLIP + face recognition on your laptop, with App Service as backup",
             "active": brain["enabled"], "healthy": brain["ready"] and not brain["failed"], "latency_ms": None,
             "detail": ai_detail,
             "error": f"{brain['failed']} photos could not be analysed" if brain["failed"] else None},
        ],
    }


# --- The website ---------------------------------------------------------------

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def website(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found.")
    file = STATIC_DIR / path
    if path and file.is_file() and STATIC_DIR in file.resolve().parents:
        return FileResponse(file)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return Response(
        "The website has not been built yet. Run:  cd frontend  then  npm install  and  npm run build",
        media_type="text/plain",
    )
