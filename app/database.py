"""Database tables, using SQLAlchemy so the same code works with PostgreSQL (Azure) and SQLite (local).

photos  - one row per uploaded photo, plus its AI description (CLIP numbers)
matches - pairs of photos that are copies ("exact"), look alike ("similar") or show the same subject ("subject")
faces   - faces found in photos, each linked to a person
people  - groups of faces that belong to the same person
workers - which computers are running the AI right now
albums, album_photos - albums made by the user
counters - running totals, such as the space freed by deleting duplicates
settings - choices made on the website, such as where the AI runs
"""

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.exc import DatabaseError
from sqlalchemy.pool import NullPool

from app.config import database_url

metadata = MetaData()

photos = Table(
    "photos", metadata,
    Column("id", String(32), primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(50), nullable=False),
    Column("size", BigInteger, nullable=False),
    Column("width", Integer, nullable=False),
    Column("height", Integer, nullable=False),
    Column("sha256", String(64), nullable=False, index=True),
    Column("phash", String(16), nullable=False),
    Column("dhash", String(16), nullable=False),
    Column("uploaded_at", String(40), nullable=False),  # ISO 8601 text, sorts correctly
    Column("clip", LargeBinary, nullable=True),          # 512 float32 numbers from CLIP
    Column("ai_status", String(12), nullable=True, index=True),  # NULL = waiting, 'processing', 'done', 'failed'
    Column("ai_worker", String(100), nullable=True),              # which worker is analysing it
    Column("taken_at", String(40), nullable=True),                # camera date from EXIF, if any
    Column("sharpness", Float, nullable=True),                    # higher is sharper
    Column("favorite", Boolean, nullable=True),
    Column("ocr_text", Text, nullable=True),                      # words read from the photo ("" = none)
    Column("ocr_words", Text, nullable=True),                     # the same words with where they are (JSON)
    Column("flatness", Float, nullable=True),                     # share of flat colour; high for screenshots
)

albums = Table(
    "albums", metadata,
    Column("id", String(32), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("created_at", String(40), nullable=False),
)

album_photos = Table(
    "album_photos", metadata,
    Column("album_id", String(32), ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True),
    Column("photo_id", String(32), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True, index=True),
)

settings = Table(
    "settings", metadata,
    Column("name", String(40), primary_key=True),
    Column("value", String(200), nullable=False),
)

counters = Table(
    "counters", metadata,
    Column("name", String(40), primary_key=True),
    Column("value", BigInteger, nullable=False),
)

# AI workers (the website on Azure, or your laptop) report here every few seconds.
workers = Table(
    "workers", metadata,
    Column("name", String(100), primary_key=True),
    Column("kind", String(10), nullable=False),  # 'cloud' or 'laptop'
    Column("last_seen", String(40), nullable=False),
)

matches = Table(
    "matches", metadata,
    Column("photo_a", String(32), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True),
    Column("photo_b", String(32), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("kind", String(10), nullable=False),  # 'exact', 'similar' or 'subject'
    Column("similarity", Float, nullable=False),  # 0.0 to 1.0
)

people = Table(
    "people", metadata,
    Column("id", String(32), primary_key=True),
    Column("name", String(100), nullable=True),
    Column("created_at", String(40), nullable=False),
    Column("manual", Boolean, nullable=True),  # merged or split by hand: never merged automatically again
)

faces = Table(
    "faces", metadata,
    Column("id", String(32), primary_key=True),
    Column("photo_id", String(32), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("person_id", String(32), ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True),
    Column("x", Float, nullable=False),  # position and size as fractions of the photo
    Column("y", Float, nullable=False),
    Column("w", Float, nullable=False),
    Column("h", Float, nullable=False),
    Column("embedding", LargeBinary, nullable=False),  # 128 float32 numbers from SFace
)


@lru_cache(maxsize=4)
def _engine(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, poolclass=NullPool, connect_args={"timeout": 30})

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys = ON")

        return engine
    # A query waiting on a lock gives up after 30 s instead of hanging, and a transaction left open
    # by a stuck thread is closed after 5 minutes, so one problem can't freeze the AI worker.
    limits = "-c lock_timeout=30000 -c idle_in_transaction_session_timeout=300000"
    return create_engine(url, pool_pre_ping=True, pool_size=5, connect_args={"options": limits})


def engine():
    return _engine(database_url())


@contextmanager
def connect():
    """A database connection inside a transaction (committed at the end)."""
    with engine().begin() as conn:
        yield conn


def init_db() -> None:
    """Create missing tables, and add columns that newer versions introduced to existing tables."""
    eng = engine()
    try:
        metadata.create_all(eng)
    except DatabaseError:  # another process (the website or a laptop worker) created them at the same moment
        metadata.create_all(eng)
    existing = {table: {c["name"] for c in inspect(eng).get_columns(table)} for table in metadata.tables}
    with eng.begin() as conn:
        for table in metadata.sorted_tables:
            for column in table.columns:
                if column.name not in existing[table.name]:
                    column_type = column.type.compile(dialect=eng.dialect)
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}"))
