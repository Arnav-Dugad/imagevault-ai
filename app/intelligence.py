"""Uses the free AI models (app/ai.py) to understand photos: who is in them and what they show.

Analysis runs in a background worker, so uploads stay fast:
  1. CLIP describes the photo           -> smart search, "same subject" suggestions
  2. YuNet finds faces, SFace describes -> faces are grouped into people
  3. PP-OCR finds text, CRNN reads it   -> words in the photo are searchable

The worker runs inside the website, and can also run on your laptop (python -m app.worker), which
talks to the website over HTTPS. While a laptop worker is online, the website leaves new photos to it
("edge computing"), which keeps the small free App Service plan light. If the laptop is off, the website
does the work. A switch on the Cloud page can also keep the work on one side only.

The thresholds below were measured on real photos (see docs/how-it-works.md).
"""

import base64
import io
import logging
import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import bindparam, text

from app import ai, photos
from app.database import connect
from app.storage import get_storage, original_key

log = logging.getLogger("imagevault")

SAME_PERSON = 0.363   # SFace cosine similarity; OpenCV's recommended value for "same person"
SAME_SUBJECT = 0.82   # CLIP cosine similarity for "different photos of the same subject"
SEARCH_MIN = 0.015     # how much better the search must describe a photo than a generic caption does
SEARCH_WINDOW = 0.045  # results must also be close to the best result
GENERIC_CAPTIONS = ["a photo.", "a photo of something.", "a picture.", "an image."]

HEARTBEAT_SECONDS = 5          # workers report "I'm alive" this often
ONLINE_SECONDS = 20            # a worker not heard from for this long is considered offline
LAPTOP_GRACE_SECONDS = 300     # if a photo waits this long, the website analyses it even when a laptop is online
STALE_CLAIM_SECONDS = 600      # photos claimed by a worker that went silent are retried

_wake = threading.Event()
_worker_started = False
status_message = "Starting"


def face_key(face_id: str) -> str:
    return f"faces/{face_id}.jpg"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def worker_name(kind: str) -> str:
    where = os.environ.get("WEBSITE_SITE_NAME") if kind == "cloud" else None
    return f"{kind}:{where or socket.gethostname()}"


# --- Which workers are online ------------------------------------------------------------

def heartbeat(name: str, kind: str) -> None:
    with connect() as conn:
        updated = conn.execute(text("UPDATE workers SET last_seen = :now, kind = :kind WHERE name = :name"),
                               {"now": _now(), "kind": kind, "name": name}).rowcount
        if not updated:
            conn.execute(text("INSERT INTO workers (name, kind, last_seen) VALUES (:name, :kind, :now)"),
                         {"name": name, "kind": kind, "now": _now()})


def online_workers() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(text("SELECT name, kind, last_seen FROM workers WHERE last_seen >= :since "
                                 "ORDER BY kind DESC, name"), {"since": _ago(ONLINE_SECONDS)}).mappings().all()
    return [dict(row) for row in rows]


def _laptop_online() -> bool:
    return any(worker["kind"] == "laptop" for worker in online_workers())


# --- Where the AI runs (switch on the Cloud page) -------------------------------------------
# auto   - your laptop when its worker is running, otherwise Azure (the default)
# laptop - only your laptop; new photos wait until it is on
# azure  - only Azure (App Service); a running laptop worker stays idle

AI_MODES = ("auto", "laptop", "azure")


def ai_mode() -> str:
    with connect() as conn:
        value = conn.execute(text("SELECT value FROM settings WHERE name = 'ai_mode'")).scalar()
    return value if value in AI_MODES else "auto"


def set_ai_mode(mode: str) -> None:
    if mode not in AI_MODES:
        raise ValueError(f"Unknown mode: {mode}")
    with connect() as conn:
        if not conn.execute(text("UPDATE settings SET value = :v WHERE name = 'ai_mode'"), {"v": mode}).rowcount:
            conn.execute(text("INSERT INTO settings (name, value) VALUES ('ai_mode', :v)"), {"v": mode})
    wake()


# --- Analysing one photo -------------------------------------------------------------

def _release_stale_claims() -> None:
    """Give photos back to the queue if the worker analysing them has gone silent."""
    with connect() as conn:
        conn.execute(text(
            "UPDATE photos SET ai_status = NULL, ai_worker = NULL WHERE ai_status = 'processing' AND "
            "(ai_worker IS NULL OR ai_worker NOT IN (SELECT name FROM workers WHERE last_seen >= :since))"),
            {"since": _ago(STALE_CLAIM_SECONDS)})


def claim_next(worker: str = "local", kind: str = "cloud") -> str | None:
    """Pick one photo that still needs analysing and mark it as 'processing' by this worker.

    The website leaves fresh photos to a laptop worker while one is online, and the switch on the
    Cloud page can keep the work on one side only.
    """
    mode = ai_mode()
    if (kind == "cloud" and mode == "laptop") or (kind == "laptop" and mode == "azure"):
        return None
    newest = _ago(LAPTOP_GRACE_SECONDS) if kind == "cloud" and mode == "auto" and _laptop_online() else _now()
    with connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM photos WHERE ai_status IS NULL AND uploaded_at <= :newest ORDER BY uploaded_at LIMIT 1"
        ), {"newest": newest}).first()
        if row is None:
            return None
        claimed = conn.execute(
            text("UPDATE photos SET ai_status = 'processing', ai_worker = :worker "
                 "WHERE id = :id AND ai_status IS NULL"), {"id": row.id, "worker": worker}
        ).rowcount
    return row.id if claimed else ""


def _face_crop(image: Image.Image, box) -> bytes:
    x, y, w, h = box
    margin = 0.3
    left = max(0, int((x - w * margin) * image.width))
    top = max(0, int((y - h * margin) * image.height))
    right = min(image.width, int((x + w * (1 + margin)) * image.width))
    bottom = min(image.height, int((y + h * (1 + margin)) * image.height))
    crop = image.crop((left, top, right, bottom))
    crop.thumbnail((200, 200))
    buffer = io.BytesIO()
    crop.save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def remove_empty_people(conn) -> None:
    """Forget people who no longer have any faces (their photos were deleted or moved)."""
    conn.execute(text("DELETE FROM people WHERE id NOT IN "
                      "(SELECT person_id FROM faces WHERE person_id IS NOT NULL)"))


def _assign_person(conn, embedding: np.ndarray, known: list) -> str:
    """Find the person this face belongs to (or create a new one).

    If the face looks like two different people, they are probably the same person, so they're
    merged - unless one of them was merged or split by hand, which is always respected.
    """
    best: dict[str, float] = {}
    for person, other in known:
        score = float(embedding @ other)
        if score >= SAME_PERSON and score > best.get(person, -1):
            best[person] = score
    if not best:
        person_id = uuid.uuid4().hex
        conn.execute(text("INSERT INTO people (id, name, created_at) VALUES (:id, NULL, :at)"),
                     {"id": person_id, "at": _now()})
        return person_id
    rows = {r.id: r for r in conn.execute(
        text("SELECT id, name, manual FROM people WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)), {"ids": list(best)},
    )}
    closest = max(best, key=best.get)
    if any(rows[p].manual for p in best):
        return closest  # never undo a manual merge or split
    keep = next((p for p in sorted(best, key=best.get, reverse=True) if rows[p].name), closest)
    for other in set(best) - {keep}:
        conn.execute(text("UPDATE faces SET person_id = :keep WHERE person_id = :other"),
                     {"keep": keep, "other": other})
        conn.execute(text("DELETE FROM people WHERE id = :other"), {"other": other})
    for i, (person, vector) in enumerate(known):
        if person in best:
            known[i] = (keep, vector)
    return keep


@dataclass
class FoundFace:
    box: tuple[float, float, float, float]  # x, y, width, height as fractions of the photo
    embedding: np.ndarray
    crop: bytes                             # small JPEG of the face, shown on the People page


@dataclass
class Analysis:
    """Everything the AI found in one photo. Computed on a laptop or in App Service, saved by the website."""
    clip: np.ndarray
    faces: list[FoundFace]
    taken_at: str | None
    sharpness: float
    text: str

    def to_json(self) -> dict:
        b64 = lambda data: base64.b64encode(data).decode()  # noqa: E731
        return {"clip": b64(ai.to_bytes(self.clip)), "taken_at": self.taken_at, "sharpness": self.sharpness,
                "text": self.text, "faces": [{"box": list(f.box), "embedding": b64(ai.to_bytes(f.embedding)),
                                              "crop": b64(f.crop)} for f in self.faces]}

    @classmethod
    def from_json(cls, data: dict) -> "Analysis":
        def vector(value: str, size: int) -> np.ndarray:
            numbers = ai.from_bytes(base64.b64decode(value, validate=True))
            if numbers.shape != (size,) or not np.isfinite(numbers).all():
                raise ValueError(f"expected {size} numbers")
            return numbers

        faces = []
        for f in data.get("faces", []):
            box = tuple(float(v) for v in f["box"])
            if len(box) != 4 or not all(0 <= v <= 1 for v in box):
                raise ValueError("a face box must be 4 fractions of the photo")
            faces.append(FoundFace(box, vector(f["embedding"], 128), base64.b64decode(f["crop"], validate=True)))
        return cls(vector(data["clip"], 512), faces, data.get("taken_at"), float(data.get("sharpness") or 0),
                   str(data.get("text") or "")[:4000])


def compute(data: bytes) -> Analysis:
    """Run all the AI models on one photo. This is the slow part; it needs no database."""
    raw = Image.open(io.BytesIO(data))
    date = photos.taken_at(raw)
    image = ImageOps.exif_transpose(raw).convert("RGB")
    faces = [FoundFace(f.box, f.embedding, _face_crop(image, f.box)) for f in ai.find_faces(image)]
    return Analysis(ai.image_embedding(image), faces, date, photos.sharpness(image), ai.read_text(image))


def save_analysis(photo_id: str, found: Analysis) -> bool:
    """Store what the AI found: faces become people, similar photos become "same subject" suggestions."""
    storage = get_storage()
    clip = found.clip
    with connect() as conn:
        if conn.execute(text("SELECT 1 FROM photos WHERE id = :id"), {"id": photo_id}).first() is None:
            return False  # deleted while the AI was working

        # Faces -> people. When a photo is analysed again, its faces are replaced, but each face
        # keeps the person it belonged to, so names and manual merges/splits survive.
        known = [(r.person_id, ai.from_bytes(r.embedding)) for r in conn.execute(
            text("SELECT person_id, embedding FROM faces WHERE person_id IS NOT NULL AND photo_id != :id"),
            {"id": photo_id})]
        previous = conn.execute(text("SELECT id, person_id, embedding FROM faces WHERE photo_id = :id"),
                                {"id": photo_id}).all()
        for old_face in previous:
            storage.delete(face_key(old_face.id))
        conn.execute(text("DELETE FROM faces WHERE photo_id = :id"), {"id": photo_id})
        for face in found.faces:
            face_id = uuid.uuid4().hex
            same = max(previous, default=None, key=lambda old: float(face.embedding @ ai.from_bytes(old.embedding)))
            if same is not None and same.person_id and float(face.embedding @ ai.from_bytes(same.embedding)) > 0.9:
                person_id = same.person_id
            else:
                person_id = _assign_person(conn, face.embedding, known)
            storage.save(face_key(face_id), face.crop, "image/jpeg")
            conn.execute(
                text("INSERT INTO faces (id, photo_id, person_id, x, y, w, h, embedding) "
                     "VALUES (:id, :photo, :person, :x, :y, :w, :h, :emb)"),
                {"id": face_id, "photo": photo_id, "person": person_id, "x": face.box[0], "y": face.box[1],
                 "w": face.box[2], "h": face.box[3], "emb": ai.to_bytes(face.embedding)},
            )

        # Same subject: very similar CLIP description, but not already a copy. Photos of people are
        # compared by face instead, because CLIP sees any two portraits as "the same kind of photo".
        linked = {r.other for r in conn.execute(text(
            "SELECT CASE WHEN photo_a = :id THEN photo_b ELSE photo_a END AS other FROM matches "
            "WHERE photo_a = :id OR photo_b = :id"), {"id": photo_id})}
        others = conn.execute(text(
            "SELECT id, clip, (SELECT COUNT(*) FROM faces WHERE faces.photo_id = photos.id) AS face_count "
            "FROM photos WHERE clip IS NOT NULL AND id != :id"), {"id": photo_id}).all()
        for other in others:
            if other.id in linked or (found.faces and other.face_count):
                continue
            similarity = float(clip @ ai.from_bytes(other.clip))
            if similarity >= SAME_SUBJECT:
                conn.execute(
                    text("INSERT INTO matches (photo_a, photo_b, kind, similarity) VALUES (:a, :b, 'subject', :s)"),
                    {"a": photo_id, "b": other.id, "s": round(min(similarity, 0.99), 3)},
                )
        conn.execute(text(
            "UPDATE photos SET clip = :clip, ai_status = 'done', ai_worker = NULL, ocr_text = :words, "
            "taken_at = COALESCE(taken_at, :taken), sharpness = COALESCE(sharpness, :sharp) WHERE id = :id"),
            {"clip": ai.to_bytes(clip), "id": photo_id, "taken": found.taken_at, "sharp": found.sharpness,
             "words": found.text})
        remove_empty_people(conn)
    log.info("Photo analysed", extra={"faces": len(found.faces), "words": len(found.text.split())})
    return True


def analyze_photo(photo_id: str) -> None:
    with connect() as conn:
        photo = conn.execute(text("SELECT id, sha256 FROM photos WHERE id = :id"), {"id": photo_id}).first()
    if photo is None:
        return
    save_analysis(photo_id, compute(get_storage().read(original_key(photo.sha256))))


def mark_failed(photo_id: str) -> None:
    with connect() as conn:
        conn.execute(text("UPDATE photos SET ai_status = 'failed', ai_worker = NULL WHERE id = :id"), {"id": photo_id})


def process_pending(worker: str = "local", kind: str = "cloud", on_done=None) -> int:
    """Analyse every photo that is waiting. Returns how many were analysed."""
    count = 0
    last_beat = 0.0
    while (photo_id := claim_next(worker, kind)) is not None:
        if not photo_id:
            continue  # another worker took it
        if time.monotonic() - last_beat > HEARTBEAT_SECONDS:
            heartbeat(worker, kind)
            last_beat = time.monotonic()
        try:
            analyze_photo(photo_id)
            count += 1
            if on_done:
                on_done(photo_id)
        except Exception:
            log.exception("AI analysis failed")
            mark_failed(photo_id)
    return count


# --- Background worker -------------------------------------------------------------------

def wake() -> None:
    """Called after an upload so the worker starts right away."""
    _wake.set()


def run_worker(kind: str, on_status=None, on_done=None, poll_seconds: float = 30) -> None:
    """Analyse photos forever: download the models once, then keep checking for new photos."""

    def say(message: str) -> None:
        global status_message
        status_message = message
        if on_status:
            on_status(message)

    name = worker_name(kind)
    with connect() as conn:  # photos this worker was analysing when it stopped are tried again
        conn.execute(text("UPDATE photos SET ai_status = NULL, ai_worker = NULL "
                          "WHERE ai_status = 'processing' AND ai_worker = :name"), {"name": name})
        # Photos from older versions have no sharpness score or text yet: analyse them once more.
        conn.execute(text("UPDATE photos SET ai_status = NULL "
                          "WHERE ai_status = 'done' AND (sharpness IS NULL OR ocr_text IS NULL)"))
    delay = 10
    while not ai.models_ready():
        try:
            say("Downloading AI models (about 190 MB, once)")
            ai.download_models()
        except Exception as exc:
            say(f"Could not download AI models, retrying: {exc}")
            log.warning(status_message)
            time.sleep(delay)
            delay = min(delay * 2, 600)
    say("Ready")
    while True:
        try:
            heartbeat(name, kind)
            _release_stale_claims()
            process_pending(name, kind, on_done)
        except Exception:
            log.exception("AI worker error")
        _wake.wait(timeout=poll_seconds)
        _wake.clear()


def start_worker() -> None:
    """Start the AI worker inside the website (as a background thread)."""
    global _worker_started
    if ai.enabled() and not _worker_started:
        _worker_started = True
        threading.Thread(target=run_worker, args=("cloud",), name="imagevault-ai", daemon=True).start()


def status() -> dict:
    with connect() as conn:
        counts = dict(conn.execute(text(
            "SELECT COALESCE(ai_status, 'waiting'), COUNT(*) FROM photos GROUP BY ai_status")).all())
    online = online_workers()
    laptops = [w for w in online if w["kind"] == "laptop"]
    mode = ai_mode()
    runs_on = "cloud" if mode == "azure" else "laptop" if laptops else "none" if mode == "laptop" else "cloud"
    message = status_message if ai.enabled() else "Turned off"
    if runs_on == "none":
        message = "Waiting for your laptop"
    return {
        "enabled": ai.enabled(),
        "ready": ai.enabled() and (ai.models_ready() if runs_on == "cloud" else runs_on == "laptop"),
        "message": message,
        "analysed": counts.get("done", 0),
        "waiting": counts.get("waiting", 0) + counts.get("processing", 0),
        "failed": counts.get("failed", 0),
        "mode": mode,
        "runs_on": runs_on,
        "workers": online,
    }


# --- Smart search -------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _generic_captions() -> np.ndarray:
    return np.stack([ai.text_embedding(caption) for caption in GENERIC_CAPTIONS])


def search(query: str) -> list[str]:
    """Photo IDs that match a description such as "dog on a beach", best first.

    CLIP scores are compared with how well a generic caption ("a photo.") fits the same photo.
    A photo only counts as a result if the search describes it clearly better, so a search
    for something that is not in any photo returns nothing instead of random photos.
    """
    query_vector = ai.text_embedding(f"a photo of {query.strip().rstrip('.')}.")
    with connect() as conn:
        rows = conn.execute(text("SELECT id, clip FROM photos WHERE clip IS NOT NULL")).all()
    if not rows:
        return []
    vectors = np.stack([ai.from_bytes(r.clip) for r in rows])
    scores = vectors @ query_vector - (vectors @ _generic_captions().T).max(axis=1)
    cutoff = max(SEARCH_MIN, float(scores.max()) - SEARCH_WINDOW)
    ranked = sorted(((float(s), r.id) for s, r in zip(scores, rows) if s >= cutoff), reverse=True)
    return [photo_id for _, photo_id in ranked]


# --- Auto albums ------------------------------------------------------------------------------
# Each album is a few short descriptions. A photo joins an album when one of them describes it
# clearly better than a generic caption does (the same idea as smart search).

AUTO_ALBUMS = {
    "beach": ("Beach", ["a beach with sand and sea", "the seaside"]),
    "mountains": ("Mountains", ["mountains", "a mountain landscape", "a fjord between mountains"]),
    "food": ("Food & drink", ["food", "a plate of food", "fruit", "a cup of coffee"]),
    "pets": ("Pets", ["a cat", "a dog", "a puppy", "a pet"]),
    "animals": ("Wildlife", ["a wild animal", "wildlife", "a sea creature"]),
    "city": ("City", ["a city skyline", "city buildings and streets"]),
    "landmarks": ("Landmarks", ["a famous landmark", "a palace", "a castle", "a monument"]),
    "nature": ("Nature", ["a forest", "a waterfall", "a river in nature"]),
    "snow": ("Snow", ["snow", "a snowy winter scene"]),
    "sunsets": ("Sunsets", ["a sunset", "the sky at sunset"]),
}
ALBUM_MIN = 0.02  # how much better an album description must fit than a generic caption
ALBUM_NAMES = {key: name for key, (name, _) in AUTO_ALBUMS.items()} | {"people": "People"}


@lru_cache(maxsize=1)
def _album_vectors() -> dict[str, np.ndarray]:
    return {key: np.stack([ai.text_embedding(f"a photo of {p}.") for p in prompts])
            for key, (_, prompts) in AUTO_ALBUMS.items()}


def auto_albums() -> dict[str, list[str]]:
    """{album key: [photo ids, best match first]} for every auto album that has photos."""
    with connect() as conn:
        rows = conn.execute(text("SELECT id, clip FROM photos WHERE clip IS NOT NULL ORDER BY uploaded_at")).all()
        with_faces = conn.execute(text(
            "SELECT photo_id FROM faces GROUP BY photo_id ORDER BY COUNT(*) DESC")).scalars().all()
    scored = {}  # album key -> {photo id: how well it fits}
    if rows:
        vectors = np.stack([ai.from_bytes(r.clip) for r in rows])
        baseline = (vectors @ _generic_captions().T).max(axis=1)
        for key, prompts in _album_vectors().items():
            scores = (vectors @ prompts.T).max(axis=1) - baseline
            scored[key] = {r.id: float(s) for s, r in zip(scores, rows) if s >= ALBUM_MIN}
    # An animal is either a pet or wildlife: a house cat goes to Pets, a leopard to Wildlife.
    pets, wild = scored.get("pets", {}), scored.get("animals", {})
    for photo_id in set(pets) & set(wild):
        del (wild if pets[photo_id] >= wild[photo_id] else pets)[photo_id]
    result = {key: sorted(members, key=members.get, reverse=True) for key, members in scored.items()}
    if with_faces:  # face recognition finds people far more reliably than CLIP does
        result["people"] = list(with_faces)
    return {key: ids for key, ids in result.items() if ids}


# --- Bursts: photos taken seconds apart --------------------------------------------------------

BURST_SECONDS = 10      # photos taken this close together...
BURST_SIMILARITY = 0.8  # ...that also look alike (CLIP) form a burst


def bursts() -> list[list[dict]]:
    """Groups of photos taken within a few seconds of each other that show the same scene,
    each sorted sharpest first. Needs the camera date (EXIF), which messaging apps often remove."""
    with connect() as conn:
        rows = conn.execute(text(
            "SELECT id, sha256, taken_at, sharpness, clip FROM photos "
            "WHERE taken_at IS NOT NULL AND clip IS NOT NULL ORDER BY taken_at")).mappings().all()
    groups, current, seen = [], [], set()
    for row in rows:
        if row["sha256"] in seen:  # an exact copy is a duplicate, not another shot
            continue
        seen.add(row["sha256"])
        when = datetime.fromisoformat(row["taken_at"])
        if current:
            last = current[-1]
            close = (when - datetime.fromisoformat(last["taken_at"])).total_seconds() <= BURST_SECONDS
            alike = float(ai.from_bytes(row["clip"]) @ ai.from_bytes(last["clip"])) >= BURST_SIMILARITY
            if not (close and alike):
                groups.append(current)
                current = []
        current.append(row)
    groups.append(current)
    return [sorted(({"id": r["id"], "sharpness": r["sharpness"] or 0} for r in g),
                   key=lambda r: r["sharpness"], reverse=True)
            for g in groups if len(g) > 1]
