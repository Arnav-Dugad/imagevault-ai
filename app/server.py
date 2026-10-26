"""The ImageVault web server: a JSON API plus the website itself."""

import hashlib
import hmac
import io
import json
import logging
import re
import threading
import time
import uuid
import zipfile
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

from app import __version__, ai, costs, intelligence, receipts, textinfo  # noqa: E402
from app.database import connect, init_db  # noqa: E402
from app.photos import NotAPhoto, analyze, compare, hash_distance  # noqa: E402
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
    for hidden in ("phash", "dhash", "clip", "ocr_text", "ocr_words", "ocr_search", "qr_codes", "core_hash"):
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


def _with_match(row, search: list[str] | None = None) -> dict:
    photo = _photo_json(row)
    photo["match"] = photo.pop("match_kind", None)
    if search:  # where the searched words are written in the photo, to outline them on the thumbnail
        words = json.loads(row["ocr_words"]) if row.get("ocr_words") else []
        photo["highlights"] = [w["box"] for w in words if _word_matches(w["text"], search)]
    return photo


def _word_matches(word: str, search: list[str]) -> bool:
    word = intelligence.squeeze(word)
    return any(s in word or (len(word) >= 3 and word in s) for s in search)


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


PHOTO_DATE = "COALESCE(photos.taken_at, photos.uploaded_at)"  # when it was taken, else when it was uploaded
SORTS = {
    "newest": "photos.uploaded_at DESC",
    "oldest": "photos.uploaded_at ASC",
    "taken_new": f"{PHOTO_DATE} DESC",
    "taken_old": f"{PHOTO_DATE} ASC",
    "largest": "photos.size DESC",
    "smallest": "photos.size ASC",
    "name": "LOWER(photos.filename) ASC",
}


def _album_photo_ids(album: str) -> list[str] | None:
    """Photo IDs of an auto album ("auto:pets"); None for an album made by the user."""
    if album.startswith("auto:"):
        return intelligence.auto_albums().get(album[5:], []) if ai.enabled() and ai.models_ready() else []
    return None


@app.get("/api/photos")
def list_photos(search: str = "", smart: bool = False, filter: str = "all", album: str = "",
                sort: str = "newest", date_from: str = "", date_to: str = "",
                offset: int = 0, limit: int = 60):
    """Photos, filtered and sorted. `filter` is all, duplicates or favorites; `album` is an album
    id or "auto:<key>"; dates are YYYY-MM-DD and use the camera date when the photo has one."""
    limit, offset = max(1, min(limit, 200)), max(0, offset)
    ranked = None  # IDs in a fixed order (smart search results, or an auto album)
    words = intelligence.search_words(search) if search.strip() else []  # to outline on thumbnails
    if smart and search.strip():  # AI search: "dog on a beach"
        if not (ai.enabled() and ai.models_ready()):
            raise HTTPException(503, "Smart search is still getting ready. Try again in a minute.")
        ranked = intelligence.search(search.strip())
    elif album:
        ranked = _album_photo_ids(album)

    where, params = ["1 = 1"], {}
    if search and not smart:
        where.append("(LOWER(photos.filename) LIKE :search OR photos.ocr_search LIKE :squeezed)")
        params["search"] = f"%{search.lower()}%"
        params["squeezed"] = f"%{intelligence.squeeze(search) or search.lower()}%"
    if filter == "duplicates":
        where.append(f"photos.id IN (SELECT photo_a FROM matches WHERE {COPIES} "
                     f"UNION SELECT photo_b FROM matches WHERE {COPIES})")
    elif filter == "text":  # photos with words written in them, or a QR code
        where.append("(photos.ocr_search IS NOT NULL AND photos.ocr_search != '')")
    elif filter == "favorites":
        where.append("photos.favorite = :yes")
        params["yes"] = True
    if album and ranked is None:
        where.append("photos.id IN (SELECT photo_id FROM album_photos WHERE album_id = :album)")
        params["album"] = album
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_from):
        where.append(f"SUBSTR({PHOTO_DATE}, 1, 10) >= :date_from")
        params["date_from"] = date_from
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_to):
        where.append(f"SUBSTR({PHOTO_DATE}, 1, 10) <= :date_to")
        params["date_to"] = date_to

    sql = f"SELECT {PHOTO_COLUMNS} FROM photos WHERE {' AND '.join(where)}"
    with connect() as conn:
        if ranked is not None:  # keep the AI's order, apply the other filters
            if not ranked:
                return {"total": 0, "items": []}
            rows = conn.execute(text(f"{sql} AND photos.id IN :ids").bindparams(bindparam("ids", expanding=True)),
                                {**params, "ids": ranked}).mappings().all()
            position = {photo_id: i for i, photo_id in enumerate(ranked)}
            rows = sorted(rows, key=lambda r: position[r["id"]])
            return {"total": len(rows), "items": [_with_match(r, words) for r in rows[offset:offset + limit]]}
        total = conn.execute(text(f"SELECT COUNT(*) FROM ({sql}) AS matching"), params).scalar_one()
        rows = conn.execute(text(f"{sql} ORDER BY {SORTS.get(sort, SORTS['newest'])}, photos.id "
                                 "LIMIT :limit OFFSET :offset"),
                            {**params, "limit": limit, "offset": offset}).mappings().all()
    return {"total": total, "items": [_with_match(row, words) for row in rows]}


class Fingerprints(BaseModel):
    sha256: list[str]


@app.post("/api/photos/check")
def already_stored(body: Fingerprints):
    """Which of these files (SHA-256 fingerprints, worked out in the browser) are already stored."""
    wanted = list(dict.fromkeys(h.lower() for h in body.sha256))[:500]
    if not wanted:
        return {"found": {}}
    with connect() as conn:
        rows = conn.execute(text("SELECT sha256, filename FROM photos WHERE sha256 IN :hashes ORDER BY uploaded_at")
                            .bindparams(bindparam("hashes", expanding=True)), {"hashes": wanted}).all()
    found: dict[str, str] = {}
    for sha, filename in rows:
        found.setdefault(sha, filename)
    return {"found": found}


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
                _usage_cache.clear()
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
            "taken_at": info.taken_at,
            "sharpness": info.sharpness,
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
        in_albums = conn.execute(text(
            "SELECT albums.id, albums.name FROM albums JOIN album_photos ON album_photos.album_id = albums.id "
            "WHERE album_photos.photo_id = :id ORDER BY albums.name"), {"id": photo_id}).mappings().all()
    result = _photo_json(photo)
    result["matches"] = [{"kind": m["kind"], "similarity": m["similarity"], "photo": _photo_json(m)} for m in found]
    result["people"] = [{**dict(face), "image_url": f"/api/faces/{face['id']}/image"} for face in in_photo]
    result["albums"] = [dict(a) for a in in_albums]
    result["text"] = photo["ocr_text"] or ""
    result["found"] = textinfo.find(result["text"])  # phone numbers, dates, prices, emails and links
    result["qr_codes"] = json.loads(photo["qr_codes"]) if photo["qr_codes"] else []
    result["receipt"] = receipts.read(result["text"])  # shop, date and total, if it is a receipt
    result["words"] = json.loads(photo["ocr_words"]) if photo["ocr_words"] else []
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
    _usage_cache.clear()
    face_ids = conn.execute(text("SELECT id FROM faces WHERE photo_id = :id"), {"id": photo["id"]}).scalars().all()
    for face_id in face_ids:
        storage.delete(intelligence.face_key(face_id))
    conn.execute(text("DELETE FROM faces WHERE photo_id = :id"), {"id": photo["id"]})
    intelligence.remove_empty_people(conn)
    conn.execute(text("DELETE FROM matches WHERE photo_a = :id OR photo_b = :id"), {"id": photo["id"]})
    conn.execute(text("DELETE FROM album_photos WHERE photo_id = :id"), {"id": photo["id"]})
    conn.execute(text("DELETE FROM photos WHERE id = :id"), {"id": photo["id"]})
    sha = {"sha": photo["sha256"]}
    still_used = conn.execute(text("SELECT 1 FROM photos WHERE sha256 = :sha LIMIT 1"), sha).first()
    if not still_used:  # the last copy is gone, so remove the stored files too
        storage.delete(original_key(photo["sha256"]))
        storage.delete(thumbnail_key(photo["sha256"]))


def _add_freed(conn, size: int) -> None:
    """Remember how much space deleting duplicates has freed."""
    if not conn.execute(text("UPDATE counters SET value = value + :size WHERE name = 'freed_bytes'"),
                        {"size": size}).rowcount:
        conn.execute(text("INSERT INTO counters (name, value) VALUES ('freed_bytes', :size)"), {"size": size})


@app.delete("/api/photos/{photo_id}")
def delete_photo(photo_id: str, duplicate: bool = False):
    """Delete a photo. `duplicate=true` when it is removed as a copy, to count the space saved."""
    with connect() as conn:
        photo = _get_photo(conn, photo_id)
        _delete(conn, photo)
        if duplicate:
            _add_freed(conn, photo["size"])
    log.info("Photo deleted")
    return {"ok": True}


class PhotoEdit(BaseModel):
    filename: str | None = None
    favorite: bool | None = None


@app.patch("/api/photos/{photo_id}")
def edit_photo(photo_id: str, body: PhotoEdit):
    """Rename a photo or mark it as a favourite."""
    with connect() as conn:
        _get_photo(conn, photo_id)
        if body.filename is not None:
            name = Path(body.filename.strip()).name[:255]
            if not name:
                raise HTTPException(422, "The name can't be empty.")
            conn.execute(text("UPDATE photos SET filename = :name WHERE id = :id"), {"name": name, "id": photo_id})
        if body.favorite is not None:
            conn.execute(text("UPDATE photos SET favorite = :fav WHERE id = :id"),
                         {"fav": body.favorite, "id": photo_id})
        return _photo_json(_get_photo(conn, photo_id))


class BatchAction(BaseModel):
    ids: list[str]
    action: str                      # delete, favorite, unfavorite, add_to_album, remove_from_album
    album_id: str | None = None
    new_album: str | None = None     # with add_to_album: create this album first
    duplicate: bool = False          # with delete: removed as copies (counted as space saved)


@app.post("/api/photos/batch")
def batch_action(body: BatchAction):
    """Do the same thing to many photos at once."""
    ids = list(dict.fromkeys(body.ids))[:1000]
    if not ids:
        raise HTTPException(422, "No photos selected.")
    expanding = bindparam("ids", expanding=True)
    with connect() as conn:
        photos = conn.execute(text("SELECT * FROM photos WHERE id IN :ids").bindparams(expanding),
                              {"ids": ids}).mappings().all()
        if body.action == "delete":
            for photo in photos:
                _delete(conn, photo)
            if body.duplicate:
                _add_freed(conn, sum(p["size"] for p in photos))
        elif body.action in ("favorite", "unfavorite"):
            conn.execute(text("UPDATE photos SET favorite = :fav WHERE id IN :ids").bindparams(expanding),
                         {"fav": body.action == "favorite", "ids": ids})
        elif body.action in ("add_to_album", "remove_from_album"):
            album_id = body.album_id
            if body.action == "add_to_album" and body.new_album:
                album_id = _create_album(conn, body.new_album)
            if not album_id or not conn.execute(text("SELECT 1 FROM albums WHERE id = :id"), {"id": album_id}).first():
                raise HTTPException(404, "Album not found.")
            conn.execute(text("DELETE FROM album_photos WHERE album_id = :album AND photo_id IN :ids")
                         .bindparams(expanding), {"album": album_id, "ids": ids})
            if body.action == "add_to_album":
                conn.execute(text("INSERT INTO album_photos (album_id, photo_id) VALUES (:album, :photo)"),
                             [{"album": album_id, "photo": p["id"]} for p in photos])
        else:
            raise HTTPException(422, f"Unknown action: {body.action}")
    log.info("Batch action", extra={"action": body.action, "photos": len(photos)})
    return {"done": len(photos)}


@app.get("/api/zip")
def download_zip(ids: str):
    """Download several photos as one ZIP file (up to 100 at a time)."""
    wanted = [i for i in ids.split(",") if i][:100]
    with connect() as conn:
        rows = conn.execute(text("SELECT * FROM photos WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
                            {"ids": wanted}).mappings().all()
    if not rows:
        raise HTTPException(404, "No photos found.")
    buffer, used = io.BytesIO(), set()
    storage = get_storage()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:  # photos are already compressed
        for row in rows:
            name, n = row["filename"], 1
            while name.lower() in used:  # two photos with the same name: "name (2).jpg"
                n += 1
                name = f"{Path(row['filename']).stem} ({n}){Path(row['filename']).suffix}"
            used.add(name.lower())
            archive.writestr(name, storage.read(original_key(row["sha256"])))
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="imagevault-{len(rows)}-photos.zip"'})


# --- Albums ----------------------------------------------------------------------------------

def _create_album(conn, name: str) -> str:
    name = name.strip()[:100]
    if not name:
        raise HTTPException(422, "The album needs a name.")
    album_id = uuid.uuid4().hex
    conn.execute(text("INSERT INTO albums (id, name, created_at) VALUES (:id, :name, :at)"),
                 {"id": album_id, "name": name, "at": datetime.now(timezone.utc).isoformat()})
    return album_id


class AlbumBody(BaseModel):
    name: str


@app.get("/api/albums")
def list_albums():
    """Albums made by the user, and albums made automatically by the AI."""
    with connect() as conn:
        mine = conn.execute(text(
            "SELECT albums.id, albums.name, COUNT(photos.id) AS count, COALESCE(SUM(photos.size), 0) AS bytes, "
            "(SELECT ap.photo_id FROM album_photos ap WHERE ap.album_id = albums.id LIMIT 1) AS cover_id "
            "FROM albums LEFT JOIN album_photos ON album_photos.album_id = albums.id "
            "LEFT JOIN photos ON photos.id = album_photos.photo_id "
            "GROUP BY albums.id, albums.name, albums.created_at ORDER BY albums.created_at DESC")).mappings().all()
        sizes = dict(conn.execute(text("SELECT id, size FROM photos")).all())
    auto = []
    if ai.enabled() and ai.models_ready():
        for key, ids in intelligence.auto_albums().items():
            auto.append({"id": f"auto:{key}", "name": intelligence.ALBUM_NAMES[key], "count": len(ids),
                         "bytes": sum(sizes.get(i, 0) for i in ids), "cover_id": ids[0]})
    cover = lambda a: {**dict(a), "cover_url": f"/api/photos/{a['cover_id']}/thumb" if a["cover_id"] else None}  # noqa: E731
    return {"mine": [cover(a) for a in mine], "auto": [cover(a) for a in auto]}


class PhotoIds(BaseModel):
    ids: list[str]


@app.post("/api/albums/suggest")
def suggest_album_names(body: PhotoIds):
    """Names for an album of these photos, from the words written in them, what they show and when they
    were taken. For example "Malibu", "Beach" or "May 2025"."""
    ids = list(dict.fromkeys(body.ids))[:500]
    if not ids:
        return {"names": []}
    with connect() as conn:
        rows = conn.execute(text("SELECT id, ocr_text, taken_at, uploaded_at FROM photos WHERE id IN :ids")
                            .bindparams(bindparam("ids", expanding=True)), {"ids": ids}).mappings().all()
    names: list[str] = []
    # 1. A word written in several of the photos (or the clearest word, for one photo), like a place name.
    counts: dict[str, tuple[int, str]] = {}
    for row in rows:
        seen = set()
        for word in re.findall(r"[^\W\d_]{3,}", row["ocr_text"] or ""):
            key = word.lower()
            if key not in seen and key not in intelligence.COMMON_WORDS | NOT_NAMES:
                seen.add(key)
                count, shown = counts.get(key, (0, word))
                counts[key] = (count + 1, shown if shown[:1].isupper() else word)
    needed = 2 if len(rows) > 1 else 1
    for key, (count, shown) in sorted(counts.items(), key=lambda c: -c[1][0])[:2]:
        if count >= needed:
            names.append(shown if not shown.isupper() else shown.title())
    # 2. The automatic album most of them are in.
    if ai.enabled() and ai.models_ready():
        albums = intelligence.auto_albums()
        best = max(albums.items(), key=lambda a: len(set(a[1]) & set(ids)), default=None)
        if best and len(set(best[1]) & set(ids)) * 2 >= len(rows) and best[0] != "people":
            names.append(intelligence.ALBUM_NAMES[best[0]])
    # 3. When they were taken (camera dates only; the upload date says nothing): one month, or one year.
    months = {row["taken_at"][:7] for row in rows if row["taken_at"]}
    if len(months) == 1:
        names.append(datetime.strptime(months.pop(), "%Y-%m").strftime("%B %Y"))
    elif months and len({m[:4] for m in months}) == 1:
        names.append(next(iter(months))[:4])
    return {"names": list(dict.fromkeys(names))[:4]}


NOT_NAMES = {"total", "cash", "price", "time", "date", "open", "closed", "sale", "offer", "welcome", "exit",
             "entry", "street", "road", "this", "that", "your", "with", "from", "have", "will", "the", "and",
             "for", "you", "are", "not", "all", "our", "new", "get", "one", "two", "off", "per", "net", "qty"}


@app.post("/api/albums", status_code=201)
def create_album(body: AlbumBody):
    with connect() as conn:
        return {"id": _create_album(conn, body.name), "name": body.name.strip()[:100]}


@app.patch("/api/albums/{album_id}")
def rename_album(album_id: str, body: AlbumBody):
    name = body.name.strip()[:100]
    if not name:
        raise HTTPException(422, "The album needs a name.")
    with connect() as conn:
        renamed = conn.execute(text("UPDATE albums SET name = :name WHERE id = :id"), {"name": name, "id": album_id})
        if not renamed.rowcount:
            raise HTTPException(404, "Album not found.")
    return {"id": album_id, "name": name}


@app.delete("/api/albums/{album_id}")
def delete_album(album_id: str):
    """Delete an album. The photos in it are kept."""
    with connect() as conn:
        conn.execute(text("DELETE FROM album_photos WHERE album_id = :id"), {"id": album_id})
        conn.execute(text("DELETE FROM albums WHERE id = :id"), {"id": album_id})
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
            text(f"SELECT {PHOTO_COLUMNS} FROM photos ORDER BY uploaded_at DESC LIMIT 10")
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


BLOB_PRICE_PER_GB = 0.02  # US$ per GB per month (shown in rupees), Azure Blob Storage (Hot, LRS), rounded up
_usage_cache: dict = {}


@app.get("/api/storage")
def storage_usage():
    """What the photos take up in storage, what that costs, and what deleting duplicates saved."""
    storage = get_storage()
    cached = _usage_cache.get(storage.description)
    if not cached or time.monotonic() - cached[0] > 300:  # listing every file is slow, so keep it a while
        cached = _usage_cache[storage.description] = (time.monotonic(), storage.usage())
    parts = cached[1]
    with connect() as conn:
        total, stored = conn.execute(text(
            "SELECT COALESCE(SUM(size), 0), "
            "(SELECT COALESCE(SUM(size), 0) FROM (SELECT MAX(size) AS size FROM photos GROUP BY sha256) AS u) "
            "FROM photos")).one()
        freed = conn.execute(text("SELECT value FROM counters WHERE name = 'freed_bytes'")).scalar() or 0
    used = sum(parts.values())
    saved = int(total - stored) + int(freed)
    gb = 1024 ** 3
    return {
        "kind": storage.kind,
        "total_bytes": used,
        "parts": [{"key": key, "bytes": parts.get(key, 0)} for key in ("originals", "thumbnails", "faces")],
        "price_per_gb": BLOB_PRICE_PER_GB,
        "monthly_cost": used / gb * BLOB_PRICE_PER_GB,
        "saved_bytes": saved,
        "saved_monthly": saved / gb * BLOB_PRICE_PER_GB,
        "inr_rate": costs.inr_per("USD"),
    }


class ResetBody(BaseModel):
    confirm: str


@app.post("/api/reset")
def delete_everything(body: ResetBody):
    """Delete every photo, person and album, and all stored files. Used to start a demo fresh."""
    if body.confirm != "delete everything":
        raise HTTPException(422, "Not confirmed.")
    with connect() as conn:
        for table in ("album_photos", "albums", "matches", "faces", "people", "photos", "counters"):
            conn.execute(text(f"DELETE FROM {table}"))
    get_storage().delete_all()
    _usage_cache.clear()
    log.info("Everything deleted")
    return {"ok": True}


def _sharpest(members) -> str | None:
    """The clearly sharpest photo of a group, if one stands out (15% sharper than the blurriest)."""
    scored = [m for m in members if m["sharpness"]]
    if len(scored) < 2:
        return None
    best, worst = max(scored, key=lambda m: m["sharpness"]), min(scored, key=lambda m: m["sharpness"])
    return best["id"] if best["sharpness"] >= worst["sharpness"] * 1.15 else None


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
        result.append({"id": keeper["id"], "items": items, "extra_bytes": sum(p["size"] for p in members[1:]),
                       "sharpest_id": _sharpest(members)})
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
                _add_freed(conn, photo["size"])
                removed += 1
            seen.add(photo["sha256"])
    log.info("Exact copies removed", extra={"removed": removed})
    return {"removed": removed}


@app.get("/api/receipts")
def receipt_list():
    """Every photo that looks like a receipt, with its shop, date and total, grouped by shop."""
    with connect() as conn:
        rows = conn.execute(text(f"SELECT {PHOTO_COLUMNS} FROM photos WHERE ocr_text IS NOT NULL AND ocr_text != ''"))\
            .mappings().all()
    found = []
    for row in rows:
        receipt = receipts.read(row["ocr_text"])
        if receipt:
            found.append({**receipt, "photo": _with_match(row)})
    found.sort(key=lambda r: (r["date"] or "", r["photo"]["uploaded_at"]), reverse=True)
    shops: dict[str, dict] = {}
    for item in found:
        name = item["shop"] or "Unknown shop"
        key = intelligence.squeeze(name)[:16] or "unknown"
        shop = shops.setdefault(key, {"name": name, "receipts": [], "totals": {}})
        shop["receipts"].append(item)
        if item["total"] is not None:
            shop["totals"][item["currency"]] = round(shop["totals"].get(item["currency"], 0) + item["total"], 2)
    totals: dict[str, float] = {}
    for item in found:
        if item["total"] is not None:
            totals[item["currency"]] = round(totals.get(item["currency"], 0) + item["total"], 2)
    groups = sorted(shops.values(), key=lambda s: (-len(s["receipts"]), s["name"].lower()))
    return {"count": len(found), "totals": totals, "shops": groups}


MEME_SAME_PICTURE = 10  # core hashes (the middle of the picture) this close mean the same meme picture


@app.get("/api/memes")
def meme_groups():
    """Memes made from the same picture, whatever their captions say."""
    ids = intelligence.auto_albums().get("memes", []) if ai.enabled() and ai.models_ready() else []
    with connect() as conn:
        memes = _photos_by_id(conn, ids)
        hashes = dict(conn.execute(text("SELECT id, core_hash FROM photos WHERE id IN :ids")
                                   .bindparams(bindparam("ids", expanding=True)), {"ids": ids or [""]}).all())
    parent = {m["id"]: m["id"] for m in memes}

    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for i, a in enumerate(memes):
        for b in memes[i + 1:]:
            ha, hb = hashes.get(a["id"]), hashes.get(b["id"])
            if ha and hb and hash_distance(ha, hb) <= MEME_SAME_PICTURE:
                parent[root(a["id"])] = root(b["id"])
    groups: dict[str, list] = {}
    for meme in memes:
        groups.setdefault(root(meme["id"]), []).append(meme)
    return [{"id": members[0]["id"], "items": [{"kind": "meme", "similarity": 1.0, "photo": m} for m in members],
             "extra_bytes": sum(m["size"] for m in members[1:]), "sharpest_id": None}
            for members in groups.values() if len(members) > 1]


BLURRY = 45  # sharpness below this (see photos.sharpness) is very blurry; normal photos score 150+


@app.get("/api/cleanup")
def space_wasters():
    """Photos that are probably safe to delete, biggest first: lower-quality copies, the blurrier shots
    of a burst, and very blurry photos. Exact copies are left out: they are stored only once already.
    Screenshots, memes and forwarded images are listed too, but not ticked: they are often worth keeping."""
    suggestions: dict[str, dict] = {}
    counted: set[str] = set()  # identical files are stored once, so their space is counted once

    def suggest(photo: dict, reason: str, keep: dict | None = None, ticked: bool = True) -> None:
        if photo["id"] in suggestions:
            return
        freed = 0 if photo["sha256"] in counted else photo["size"]
        counted.add(photo["sha256"])
        suggestions[photo["id"]] = {"photo": photo, "reason": reason, "bytes": freed, "suggested": ticked,
                                    "keep": {"id": keep["id"], "filename": keep["filename"]} if keep else None}

    for group in duplicate_groups():
        keeper = group["items"][0]["photo"]
        for item in group["items"][1:]:
            if item["photo"]["sha256"] != keeper["sha256"]:  # copies of the best photo itself free nothing
                suggest(item["photo"], "Lower-quality copy", keeper)
    for group in burst_groups():
        keeper = group["items"][0]["photo"]
        for item in group["items"][1:]:
            suggest(item["photo"], "Blurrier shot of a burst", keeper)
    with connect() as conn:
        blurry = conn.execute(text(f"SELECT {PHOTO_COLUMNS} FROM photos WHERE sharpness < :limit"),
                              {"limit": BLURRY}).mappings().all()
        albums = intelligence.auto_albums() if ai.enabled() and ai.models_ready() else {}
        offered = {reason: _photos_by_id(conn, albums.get(key, [])) for key, reason in
                   (("screenshots", "Screenshot"), ("memes", "Meme"), ("forwarded", "Forwarded image"))}
    for row in blurry:
        suggest(_photo_json(row), "Very blurry")
    for reason, photos in offered.items():  # often worth keeping, so offered but not ticked
        for photo in photos:
            suggest(photo, reason, ticked=False)
    items = sorted(suggestions.values(), key=lambda s: (s["bytes"] or s["photo"]["size"], s["bytes"]), reverse=True)
    return {"items": items, "total_bytes": sum(s["bytes"] for s in items)}


@app.get("/api/related")
def related_groups():
    """Different photos of the same subject or scene, found by AI. These are never deleted automatically."""
    found, groups = _matched_groups("kind = 'subject'")
    in_bursts = {p["id"] for group in intelligence.bursts() for p in group} if ai.enabled() else set()
    groups = [kept for members in groups if len(kept := [p for p in members if p["id"] not in in_bursts]) > 1]
    best = {}
    for m in found:
        for photo_id in (m["photo_a"], m["photo_b"]):
            best[photo_id] = max(best.get(photo_id, 0), m["similarity"])
    result = []
    for members in groups:
        members.sort(key=lambda p: p["uploaded_at"])
        items = [{"kind": "subject", "similarity": best[p["id"]], "photo": _photo_json(p)} for p in members]
        result.append({"id": members[0]["id"], "items": items, "extra_bytes": 0, "sharpest_id": _sharpest(members)})
    result.sort(key=lambda g: len(g["items"]), reverse=True)
    return result


@app.get("/api/bursts")
def burst_groups():
    """Photos taken seconds apart that show the same scene, sharpest first: keep one, delete the rest."""
    groups = intelligence.bursts() if ai.enabled() else []
    with connect() as conn:
        result = []
        for group in groups:
            photos = _photos_by_id(conn, [g["id"] for g in group])
            if len(photos) > 1:
                result.append({"id": photos[0]["id"], "sharpest_id": photos[0]["id"], "extra_bytes":
                               sum(p["size"] for p in photos[1:]),
                               "items": [{"kind": "burst", "similarity": 1.0, "photo": p} for p in photos]})
    return result


# --- People (face recognition) -------------------------------------------------------

# People who appear in at least two different photos (one-off faces are not worth showing),
# plus anyone the user has merged or split by hand.
PEOPLE_QUERY = """
    SELECT people.id, people.name, COUNT(DISTINCT faces.photo_id) AS photos
    FROM people JOIN faces ON faces.person_id = people.id
    GROUP BY people.id, people.name, people.manual
    HAVING COUNT(DISTINCT faces.photo_id) >= 2 OR people.manual IS TRUE
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
        faces = conn.execute(text("SELECT id, photo_id FROM faces WHERE person_id = :id"),
                             {"id": person_id}).mappings().all()
    return {**dict(person), "image_url": cover, "photos": photos,
            "faces": [{**dict(f), "image_url": f"/api/faces/{f['id']}/image"} for f in faces]}


class MergePeople(BaseModel):
    ids: list[str]


@app.post("/api/people/merge")
def merge_people(body: MergePeople):
    """These people are really one person: join them. The AI won't separate them again."""
    ids = list(dict.fromkeys(body.ids))
    if len(ids) < 2:
        raise HTTPException(422, "Pick at least two people to merge.")
    with connect() as conn:
        rows = conn.execute(text("SELECT id, name FROM people WHERE id IN :ids ORDER BY created_at")
                            .bindparams(bindparam("ids", expanding=True)), {"ids": ids}).mappings().all()
        if len(rows) < 2:
            raise HTTPException(404, "Person not found.")
        keep = next((r["id"] for r in rows if r["name"]), rows[0]["id"])
        others = [r["id"] for r in rows if r["id"] != keep]
        conn.execute(text("UPDATE faces SET person_id = :keep WHERE person_id IN :others")
                     .bindparams(bindparam("others", expanding=True)), {"keep": keep, "others": others})
        conn.execute(text("DELETE FROM people WHERE id IN :others").bindparams(bindparam("others", expanding=True)),
                     {"others": others})
        conn.execute(text("UPDATE people SET manual = :yes WHERE id = :id"), {"yes": True, "id": keep})
    return {"id": keep}


class SplitPerson(BaseModel):
    face_ids: list[str]


@app.post("/api/people/{person_id}/split")
def split_person(person_id: str, body: SplitPerson):
    """These faces are someone else: move them to a new person. The AI won't join them back."""
    with connect() as conn:
        if not conn.execute(text("SELECT 1 FROM people WHERE id = :id"), {"id": person_id}).first():
            raise HTTPException(404, "Person not found.")
        new_id = uuid.uuid4().hex
        conn.execute(text("INSERT INTO people (id, name, created_at, manual) VALUES (:id, NULL, :at, :yes)"),
                     {"id": new_id, "at": datetime.now(timezone.utc).isoformat(), "yes": True})
        moved = conn.execute(text("UPDATE faces SET person_id = :new WHERE person_id = :old AND id IN :faces")
                             .bindparams(bindparam("faces", expanding=True)),
                             {"new": new_id, "old": person_id, "faces": body.face_ids or [""]}).rowcount
        if not moved:
            raise HTTPException(422, "Pick at least one face to move.")
        conn.execute(text("UPDATE people SET manual = :yes WHERE id = :id"), {"yes": True, "id": person_id})
        intelligence.remove_empty_people(conn)
    return {"id": new_id, "moved": moved}


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


class AiMode(BaseModel):
    mode: str


@app.put("/api/ai/mode")
def change_ai_mode(body: AiMode):
    """Where the AI runs: "auto" (laptop when it's on, else Azure), "laptop" or "azure"."""
    try:
        intelligence.set_ai_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    log.info("AI mode changed", extra={"mode": body.mode})
    return intelligence.status()


# --- Laptop AI worker ------------------------------------------------------------------------
# `python -m app.worker` logs in like a browser and uses these over HTTPS, so it works on any
# Wi-Fi and never needs the database password or storage keys.

class WorkerHello(BaseModel):
    name: str
    version: int = 0  # the analysis version the laptop's code produces (older workers don't send one)


@app.post("/api/worker/next")
def worker_next_photo(body: WorkerHello):
    """The laptop says it's alive and asks for the next photo to analyse (none if there's nothing to do)."""
    if body.version != intelligence.ANALYSIS_VERSION:  # older code would store incomplete results
        return {"mode": intelligence.ai_mode(), "photo": None,
                "update": "This laptop runs an older ImageVault. Update it (git pull) and restart the worker."}
    name = f"laptop:{body.name.strip()[:80] or 'laptop'}"
    intelligence.heartbeat(name, "laptop")
    intelligence.release_stale_claims()  # photos held by a worker that went silent go back in the queue
    while (photo_id := intelligence.claim_next(name, "laptop")) == "":
        pass  # another worker took that photo a moment ago: try the next one
    photo = None
    if photo_id:
        photo = {"id": photo_id, "file_url": f"/api/photos/{photo_id}/file"}
    return {"mode": intelligence.ai_mode(), "photo": photo}


@app.post("/api/worker/result/{photo_id}")
def worker_result(photo_id: str, body: dict):
    """What the laptop's AI found in a photo. The website stores it, exactly as if it had done the work."""
    if body.get("version") != intelligence.ANALYSIS_VERSION:
        intelligence.release(photo_id)  # from a laptop running older code: let an up-to-date worker redo it
        raise HTTPException(422, "This laptop runs an older ImageVault. Update it (git pull) and restart the worker.")
    try:
        found = intelligence.Analysis.from_json(body)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"Not a valid analysis: {exc}") from exc
    return {"saved": intelligence.save_analysis(photo_id, found)}


class WorkerFailure(BaseModel):
    version: int = 0


@app.post("/api/worker/failed/{photo_id}")
def worker_failed(photo_id: str, body: WorkerFailure | None = None):
    if body is None or body.version != intelligence.ANALYSIS_VERSION:
        intelligence.release(photo_id)  # an older laptop's failure says nothing about the photo
    else:
        intelligence.mark_failed(photo_id)
    return {"ok": True}


@app.get("/api/costs")
def azure_costs():
    """This month's Azure spending for the project (Azure Cost Management), cached for an hour."""
    report = costs.month_to_date()
    return {**report, "inr_rate": costs.inr_per(report.get("currency") or "USD")}


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
    where = {"laptop": "on your laptop (edge)", "cloud": "in App Service" if site else "on this computer"}
    waiting = f", {brain['waiting']} waiting" if brain["waiting"] else ""
    if brain["runs_on"] == "none":
        ai_detail = f"Waiting for your laptop{waiting}"
    elif brain["ready"]:
        ai_detail = f"Running {where[brain['runs_on']]} · {brain['analysed']} photos analysed{waiting}"
    else:
        ai_detail = brain["message"]
    return {
        "version": __version__,
        "environment": "Azure" if site else "Local",
        "build": _build_info(),
        "ai_runs_on": brain["runs_on"],
        "ai_mode": brain["mode"],
        "laptop_online": any(worker["kind"] == "laptop" for worker in brain["workers"]),
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
             "role": "Finds people, things and text in photos, on your laptop or in App Service",
             "active": brain["enabled"], "latency_ms": None,
             "healthy": (brain["ready"] or brain["runs_on"] == "none") and not brain["failed"],
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
