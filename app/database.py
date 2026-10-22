"""SQLite database with two tables.

photos  - one row per uploaded photo
matches - pairs of photos that are duplicates ("exact") or look alike ("similar")
"""

import sqlite3
from contextlib import contextmanager

from app.config import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id           TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size         INTEGER NOT NULL,
    width        INTEGER NOT NULL,
    height       INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    phash        TEXT NOT NULL,
    dhash        TEXT NOT NULL,
    storage      TEXT NOT NULL,   -- 'local' or 'azure'
    uploaded_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS photos_sha256 ON photos (sha256);

CREATE TABLE IF NOT EXISTS matches (
    photo_a    TEXT NOT NULL REFERENCES photos (id) ON DELETE CASCADE,
    photo_b    TEXT NOT NULL REFERENCES photos (id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,     -- 'exact' or 'similar'
    similarity REAL NOT NULL,     -- 0.0 to 1.0
    PRIMARY KEY (photo_a, photo_b)
);
CREATE INDEX IF NOT EXISTS matches_b ON matches (photo_b);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(data_dir() / "imagevault.db", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
