"""Disposable browser-test server; never used by the production entrypoint.

Uses real HTTP, authentication, SQLite, image validation and pixel verification.
Model inference and Blob storage are deterministic fixtures, not Azure services.
"""
import asyncio
import base64
import tempfile
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import images
from app.core.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Base
from app.services import images as summaries
from app.services.intelligence import OcrResult
from app.worker import tasks
from tests.test_images import FakeStorage

settings = get_settings()
settings.rate_limit_enabled = False
settings.registration_enabled = True
settings.registration_code = 'classroom-test'
settings.max_batch_files = 10
settings.max_video_upload_bytes = 100 * 1024 * 1024
fake = FakeStorage()
fake.get_bytes = lambda key: fake.objects[key]


def preview(key):
    data = fake.objects.get(key)
    if not data:
        return None
    mime = 'image/webp' if key.endswith('.webp') else 'image/png'
    return f'data:{mime};base64,{base64.b64encode(data).decode()}'


fake.presigned_get = preview
images.storage = summaries.storage = tasks.storage = fake
tasks.embedder = SimpleNamespace(image_embedding_frames=lambda _: (None, 0, 'fixture'))
tasks.extract_ocr_layout = lambda _: OcrResult('', None, [], None)
tasks.face_engine.analyze = lambda _: []
tasks._semantic_labels = lambda _: {}
tasks._heartbeat = lambda: None


@asynccontextmanager
async def test_lifespan(_):
    with tempfile.TemporaryDirectory(prefix='imagevault-browser-') as directory:
        engine = create_async_engine(f'sqlite+aiosqlite:///{Path(directory) / "test.sqlite"}')
        from sqlalchemy import event
        @event.listens_for(engine.sync_engine, 'connect')
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tasks.SessionLocal = factory
        async def database():
            async with factory() as db:
                yield db
        app.dependency_overrides[get_db] = database
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        def publish(image_id):
            from uuid import UUID
            loop.call_soon_threadsafe(queue.put_nowait, UUID(image_id))
        images.process_image = SimpleNamespace(delay=publish)
        async def consume():
            while True:
                image_id = await queue.get()
                await tasks._process(image_id)
                queue.task_done()
        worker = asyncio.create_task(consume())
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            app.dependency_overrides.clear()
            await engine.dispose()


app.router.lifespan_context = test_lifespan


@app.get('/__test_ready', include_in_schema=False)
async def ready():
    return {'test_server': True}


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000)
