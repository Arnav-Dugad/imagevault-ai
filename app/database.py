"""Database tables, using SQLAlchemy so the same code works with PostgreSQL (Azure) and SQLite (local).

photos  - one row per uploaded photo
matches - pairs of photos that are duplicates ("exact") or look alike ("similar")
"""

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
)
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
)

matches = Table(
    "matches", metadata,
    Column("photo_a", String(32), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True),
    Column("photo_b", String(32), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("kind", String(10), nullable=False),  # 'exact' or 'similar'
    Column("similarity", Float, nullable=False),  # 0.0 to 1.0
)


@lru_cache(maxsize=4)
def _engine(url: str):
    if url.startswith("sqlite"):
        engine = create_engine(url, poolclass=NullPool)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys = ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5)


def engine():
    return _engine(database_url())


@contextmanager
def connect():
    """A database connection inside a transaction (committed at the end)."""
    with engine().begin() as conn:
        yield conn


def init_db() -> None:
    metadata.create_all(engine())
