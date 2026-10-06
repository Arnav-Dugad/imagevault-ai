"""Exercise real pgvector retrieval in CI, with deterministic model outputs."""
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, DuplicateMatch, DuplicateType, Image, ProcessingStatus, User
from app.services.intelligence import OcrResult
from app.worker import tasks
from tests.test_images import FakeStorage
from tests.test_reliability import encoded, scene


@pytest.mark.asyncio
async def test_postgres_worker_retrieves_and_verifies_resized_copy(monkeypatch):
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('CI supplies a disposable pgvector database')
    if not url.endswith('/imagevault_test'):
        raise ValueError('Use only the disposable imagevault_test database')
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = FakeStorage()
    storage.get_bytes = lambda key: storage.objects[key]
    first, second = uuid4(), uuid4()
    storage.objects[str(first)] = encoded(scene())
    storage.objects[str(second)] = encoded(scene().resize((256, 192)))
    monkeypatch.setattr(tasks, 'SessionLocal', factory)
    monkeypatch.setattr(tasks, 'storage', storage)
    monkeypatch.setattr(tasks, 'embedder', SimpleNamespace(image_embedding_frames=lambda _: ([1.] + [0.] * 511, 0, 'test')))
    monkeypatch.setattr(tasks, '_semantic_labels', lambda _: {})
    monkeypatch.setattr(tasks, 'extract_ocr_layout', lambda _: OcrResult('', None, [], None))
    monkeypatch.setattr(tasks.face_engine, 'analyze', lambda _: [])
    monkeypatch.setattr(tasks, '_heartbeat', lambda: None)
    try:
        async with factory() as db:
            user = User(email='pgvector@example.com', display_name='Test', password_hash='unused')
            db.add(user)
            await db.flush()
            for n, image_id in enumerate((first, second)):
                db.add(Image(id=image_id, user_id=user.id, original_filename=f'{n}.png',
                             object_key=str(image_id), thumbnail_key=f'thumb-{image_id}',
                             mime_type='image/png', file_size=len(storage.objects[str(image_id)]),
                             sha256=str(n) * 64, status=ProcessingStatus.PENDING))
            await db.commit()
        await tasks._process(first)
        await tasks._process(second)
        async with factory() as db:
            matches = list((await db.scalars(select(DuplicateMatch))).all())
            assert len(matches) == 1 and matches[0].match_type == DuplicateType.PERCEPTUAL
            assert matches[0].clip_score == pytest.approx(1)
            assert 'Aligned pixels verified at two scales' in matches[0].evidence
            original = await db.get(Image, first)
            assert original.embedding.shape == (512,)
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


def test_postgres_migrations_upgrade_and_rollback_cleanup_table():
    import subprocess
    import sys
    from pathlib import Path
    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('CI supplies a disposable pgvector database')
    if not url.endswith('/imagevault_test'):
        raise ValueError('Use only the disposable imagevault_test database')
    env = {**os.environ, 'DATABASE_URL': url}
    backend = Path(__file__).resolve().parents[1]
    def migrate(*arguments):
        result = subprocess.run([sys.executable, '-m', 'alembic', *arguments], cwd=backend,
                                env=env, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
    try:
        migrate('upgrade', 'head')
        migrate('downgrade', '0005')
        migrate('upgrade', 'head')
    finally:
        migrate('downgrade', 'base')
