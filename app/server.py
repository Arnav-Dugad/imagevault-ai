"""The ImageVault web server: a small JSON API plus the website itself."""

import hashlib
import hmac
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.config import MAX_UPLOAD_BYTES, app_password, azure_settings, data_dir, load_settings, save_settings
from app.database import connect, init_db
from app.photos import NotAPhoto, analyze, compare
from app.storage import AzureBlobStorage, active_storage, get_storage

STATIC_DIR = (Path(__file__).parent / "static").resolve()
SESSION_COOKIE = "imagevault_session"

app = FastAPI(title="ImageVault", version=__version__)
init_db()


# --- Optional password (only used when APP_PASSWORD is set) -----------------

def _session_token(password: str) -> str:
    return hmac.new(password.encode(), b"imagevault-session", hashlib.sha256).hexdigest()


def _logged_in(request: Request) -> bool:
    password = app_password()
    if not password:
        return True
    cookie = request.cookies.get(SESSION_COOKIE, "")
    return hmac.compare_digest(cookie, _session_token(password))


@app.middleware("http")
async def require_password(request: Request, call_next):
    path = request.url.path
    public = path in ("/api/session", "/api/login") or not path.startswith("/api/")
    if not public and not _logged_in(request):
        return JSONResponse({"detail": "Please log in."}, status_code=401)
    return await call_next(request)


class Login(BaseModel):
    password: str


@app.get("/api/session")
def session(request: Request):
    return {"password_required": bool(app_password()), "logged_in": _logged_in(request)}


@app.post("/api/login")
def login(body: Login, request: Request):
    password = app_password()
    if password and not hmac.compare_digest(body.password, password):
        raise HTTPException(401, "Wrong password.")
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

def _thumb_path(photo_id: str) -> Path:
    return data_dir() / "thumbs" / f"{photo_id}.jpg"


def _photo_json(row) -> dict:
    photo = dict(row)
    photo.pop("phash", None)
    photo.pop("dhash", None)
    photo["thumb_url"] = f"/api/photos/{row['id']}/thumb"
    photo["file_url"] = f"/api/photos/{row['id']}/file"
    return photo


def _get_photo(conn, photo_id: str):
    row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Photo not found.")
    return row


# Adds a "match" column: 'exact', 'similar' or NULL, so the gallery can show a badge.
PHOTO_COLUMNS = """
    photos.*,
    (SELECT CASE WHEN COUNT(*) = 0 THEN NULL WHEN SUM(kind = 'exact') > 0 THEN 'exact' ELSE 'similar' END
       FROM matches WHERE photo_a = photos.id OR photo_b = photos.id) AS match
"""


@app.get("/api/photos")
def list_photos(search: str = "", duplicates_only: bool = False, offset: int = 0, limit: int = 60):
    where = "WHERE filename LIKE ?"
    if duplicates_only:
        where += " AND id IN (SELECT photo_a FROM matches UNION SELECT photo_b FROM matches)"
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM photos {where}", (f"%{search}%",)).fetchone()[0]
        rows = conn.execute(
            f"SELECT {PHOTO_COLUMNS} FROM photos {where} ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
            (f"%{search}%", min(limit, 200), offset),
        ).fetchall()
    return {"total": total, "items": [_photo_json(row) for row in rows]}


@app.post("/api/photos", status_code=201)
def upload_photo(file: UploadFile = File(...)):
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "This photo is larger than 25 MB.")
    try:
        info = analyze(data)
    except NotAPhoto as exc:
        raise HTTPException(415, str(exc)) from exc

    storage = active_storage()
    with connect() as conn:
        already_stored = conn.execute(
            "SELECT 1 FROM photos WHERE sha256 = ? AND storage = ?", (info.sha256, storage.name)
        ).fetchone()
        if not already_stored:
            try:
                storage.save(info.sha256, data, info.content_type)
            except Exception as exc:
                raise HTTPException(502, f"Could not save the photo to {storage.name} storage: {exc}") from exc

        photo = {
            "id": uuid.uuid4().hex,
            "filename": Path(file.filename or "photo").name,
            "content_type": info.content_type,
            "size": len(data),
            "width": info.width,
            "height": info.height,
            "sha256": info.sha256,
            "phash": info.phash,
            "dhash": info.dhash,
            "storage": storage.name,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.execute(
            f"INSERT INTO photos ({', '.join(photo)}) VALUES ({', '.join('?' * len(photo))})",
            tuple(photo.values()),
        )
        thumb = _thumb_path(photo["id"])
        thumb.parent.mkdir(exist_ok=True)
        thumb.write_bytes(info.thumbnail)

        # Compare the new photo with every photo already in the vault.
        best = None
        others = conn.execute(
            "SELECT id, filename, sha256, phash, dhash, width, height FROM photos WHERE id != ?", (photo["id"],)
        ).fetchall()
        for other in others:
            result = compare(photo, dict(other))
            if result is None:
                continue
            kind, similarity = result
            conn.execute(
                "INSERT INTO matches (photo_a, photo_b, kind, similarity) VALUES (?, ?, ?, ?)",
                (photo["id"], other["id"], kind, similarity),
            )
            if best is None or similarity > best["similarity"]:
                best = {"id": other["id"], "filename": other["filename"], "kind": kind, "similarity": similarity}

    return {"photo": _photo_json(photo), "match": best}


@app.get("/api/photos/{photo_id}")
def photo_details(photo_id: str):
    with connect() as conn:
        photo = _get_photo(conn, photo_id)
        matches = conn.execute(
            """SELECT photos.*, matches.kind, matches.similarity FROM matches
               JOIN photos ON photos.id = CASE WHEN matches.photo_a = ? THEN matches.photo_b ELSE matches.photo_a END
               WHERE matches.photo_a = ? OR matches.photo_b = ?
               ORDER BY matches.similarity DESC""",
            (photo_id, photo_id, photo_id),
        ).fetchall()
    result = _photo_json(photo)
    result["matches"] = [
        {"kind": m["kind"], "similarity": m["similarity"], "photo": _photo_json(m)} for m in matches
    ]
    return result


@app.get("/api/photos/{photo_id}/thumb")
def photo_thumbnail(photo_id: str):
    path = _thumb_path(photo_id)
    if not path.exists():
        raise HTTPException(404, "Thumbnail not found.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/photos/{photo_id}/file")
def photo_file(photo_id: str, download: bool = False):
    with connect() as conn:
        photo = _get_photo(conn, photo_id)
    try:
        data = get_storage(photo["storage"]).read(photo["sha256"])
    except Exception as exc:
        raise HTTPException(502, f"Could not load the photo from {photo['storage']} storage: {exc}") from exc
    disposition = "attachment" if download else "inline"
    safe_name = re.sub(r'[^\w.\- ]', "_", photo["filename"])
    headers = {
        "Content-Disposition": f'{disposition}; filename="{safe_name}"',
        "Cache-Control": "private, max-age=86400",
    }
    return Response(data, media_type=photo["content_type"], headers=headers)


def _delete(conn, photo) -> None:
    conn.execute("DELETE FROM photos WHERE id = ?", (photo["id"],))
    _thumb_path(photo["id"]).unlink(missing_ok=True)
    still_used = conn.execute(
        "SELECT 1 FROM photos WHERE sha256 = ? AND storage = ?", (photo["sha256"], photo["storage"])
    ).fetchone()
    if not still_used:
        try:
            get_storage(photo["storage"]).delete(photo["sha256"])
        except RuntimeError:
            pass  # Azure is disconnected; the record is removed but the file stays in Azure.


@app.delete("/api/photos/{photo_id}")
def delete_photo(photo_id: str):
    with connect() as conn:
        _delete(conn, _get_photo(conn, photo_id))
    return {"ok": True}


# --- Dashboard and duplicate review --------------------------------------------

@app.get("/api/stats")
def stats():
    with connect() as conn:
        total, total_bytes = conn.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM photos").fetchone()
        stored_bytes = conn.execute(
            "SELECT COALESCE(SUM(size), 0) FROM (SELECT MAX(size) AS size FROM photos GROUP BY sha256, storage)"
        ).fetchone()[0]
        unique = conn.execute("SELECT COUNT(DISTINCT sha256) FROM photos").fetchone()[0]
        similar = conn.execute("SELECT COUNT(*) FROM matches WHERE kind = 'similar'").fetchone()[0]
        recent = conn.execute(f"SELECT {PHOTO_COLUMNS} FROM photos ORDER BY uploaded_at DESC LIMIT 8").fetchall()
    return {
        "photos": total,
        "total_bytes": total_bytes,
        "stored_bytes": stored_bytes,
        "saved_bytes": total_bytes - stored_bytes,
        "exact_copies": total - unique,
        "similar_pairs": similar,
        "storage": active_storage().name,
        "recent": [_photo_json(row) for row in recent],
    }


@app.get("/api/duplicates")
def duplicate_groups():
    """Group photos that are linked by matches. The best copy of each group is listed first."""
    with connect() as conn:
        matches = conn.execute("SELECT * FROM matches").fetchall()
        ids = {m["photo_a"] for m in matches} | {m["photo_b"] for m in matches}
        rows = conn.execute(
            f"SELECT * FROM photos WHERE id IN ({', '.join('?' * len(ids))})", tuple(ids)
        ).fetchall()
    photos = {row["id"]: row for row in rows}

    # Union-find: put photos that match each other into the same group.
    parent = {photo_id: photo_id for photo_id in photos}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in matches:
        parent[root(m["photo_a"])] = root(m["photo_b"])
    groups: dict[str, list] = {}
    for photo_id in photos:
        groups.setdefault(root(photo_id), []).append(photos[photo_id])

    best_match = {}
    for m in matches:
        for photo_id in (m["photo_a"], m["photo_b"]):
            if photo_id not in best_match or m["similarity"] > best_match[photo_id]["similarity"]:
                best_match[photo_id] = {"kind": m["kind"], "similarity": m["similarity"]}

    result = []
    for members in groups.values():
        # Keep the largest photo; if equal, keep the one uploaded first.
        members.sort(key=lambda p: (-(p["width"] * p["height"]), -p["size"], p["uploaded_at"]))
        keeper = members[0]
        items = []
        for photo in members:
            if photo is keeper:
                relation = {"kind": "keep", "similarity": 1.0}
            elif photo["sha256"] == keeper["sha256"]:
                relation = {"kind": "exact", "similarity": 1.0}
            else:
                relation = best_match[photo["id"]]
            items.append({**relation, "photo": _photo_json(photo)})
        extra_bytes = sum(p["size"] for p in members[1:])
        result.append({"id": keeper["id"], "items": items, "extra_bytes": extra_bytes})
    result.sort(key=lambda g: max(i["photo"]["uploaded_at"] for i in g["items"]), reverse=True)
    return result


@app.post("/api/duplicates/remove-exact")
def remove_exact_copies():
    """Delete every exact copy, keeping the first upload of each photo."""
    removed = 0
    with connect() as conn:
        rows = conn.execute("SELECT * FROM photos ORDER BY uploaded_at").fetchall()
        seen = set()
        for photo in rows:
            if photo["sha256"] in seen:
                _delete(conn, photo)
                removed += 1
            seen.add(photo["sha256"])
    return {"removed": removed}


# --- Settings (Azure connection) -----------------------------------------------

class AzureConnection(BaseModel):
    connection_string: str
    container: str = "photos"


@app.get("/api/settings")
def get_settings():
    connection_string, container, from_env = azure_settings()
    account = None
    if connection_string:
        match = re.search(r"AccountName=([^;]+)", connection_string)
        account = match.group(1) if match else None
    return {
        "version": __version__,
        "storage": "azure" if connection_string else "local",
        "azure_account": account,
        "azure_container": container,
        "azure_set_by_environment": from_env,
        "data_folder": str(data_dir()),
    }


@app.put("/api/settings/azure")
def connect_azure(body: AzureConnection):
    if azure_settings()[2]:
        raise HTTPException(409, "Azure is configured by the server's environment variables.")
    connection_string = body.connection_string.strip()
    container = body.container.strip().lower()
    if not re.fullmatch(r"[a-z0-9](?!.*--)[a-z0-9-]{1,61}[a-z0-9]", container):
        raise HTTPException(422, "Container names use 3-63 lowercase letters, numbers and single hyphens.")
    if "AccountName=" not in connection_string or "AccountKey=" not in connection_string:
        raise HTTPException(
            422, "That does not look like a connection string. Copy it from Azure Portal > "
                 "your storage account > Security + networking > Access keys.",
        )
    try:
        AzureBlobStorage(connection_string, container).check()
    except Exception as exc:
        raise HTTPException(400, f"Azure did not accept the connection: {exc}") from exc
    settings = load_settings()
    settings.update(azure_connection_string=connection_string, azure_container=container)
    save_settings(settings)
    return get_settings()


@app.delete("/api/settings/azure")
def disconnect_azure():
    if azure_settings()[2]:
        raise HTTPException(409, "Azure is configured by the server's environment variables.")
    settings = load_settings()
    settings.pop("azure_connection_string", None)
    settings.pop("azure_container", None)
    save_settings(settings)
    return get_settings()


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
