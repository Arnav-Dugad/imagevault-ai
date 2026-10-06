from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from sqlalchemy import select

import app.api.images as routes
import app.services.images as media
from app.core.config import get_settings
from app.models import Image, ProcessingJob
from tests.conftest import create_user
from tests.test_images import FakeStorage, png_bytes


@pytest.fixture
async def vault(client, monkeypatch):
    auth = await create_user(client)
    fake = FakeStorage()
    monkeypatch.setattr(routes, 'storage', fake)
    monkeypatch.setattr(media, 'storage', fake)
    monkeypatch.setattr(routes, 'process_image', SimpleNamespace(delay=lambda _: None))
    return {'Authorization': f"Bearer {auth['access_token']}"}, fake, auth


async def upload(client, headers, name='photo.png', data=None, mime='image/png'):
    return await client.post('/api/images/upload', headers=headers,
                             files=[('files', (name, data or png_bytes(), mime))])


@pytest.mark.asyncio
async def test_actual_photo_limit_cannot_be_bypassed_with_video_extension(client, vault, monkeypatch):
    headers, fake, _ = vault
    monkeypatch.setattr(get_settings(), 'max_upload_bytes', len(png_bytes()) - 1)
    response = await upload(client, headers, 'disguised.mp4', mime='application/octet-stream')
    assert response.status_code == 413
    assert not fake.objects
    assert (await client.get('/api/images', headers=headers)).json()['total'] == 0


@pytest.mark.asyncio
async def test_worker_outage_marks_saved_upload_retryable(client, vault, session_factory, monkeypatch):
    headers, fake, _ = vault
    def unavailable(_):
        raise ConnectionError('broker unavailable')
    monkeypatch.setattr(routes, 'process_image', SimpleNamespace(delay=unavailable))
    response = await upload(client, headers)
    assert response.status_code == 202
    item = response.json()['items'][0]
    assert item['image']['status'] == 'FAILED'
    assert 'retry' in item['message'].lower()
    assert len(fake.objects) == 1  # original is safely retained
    async with session_factory() as db:
        job = await db.scalar(select(ProcessingJob))
        assert job.status.value == 'FAILED'
    monkeypatch.setattr(routes, 'process_image', SimpleNamespace(delay=lambda _: None))
    retry = await client.post('/api/images/reindex', headers=headers)
    assert retry.json()['queued'] == 1
    assert retry.json()['failed'] == 0


@pytest.mark.asyncio
async def test_smart_search_broker_failure_is_service_unavailable(client, vault, monkeypatch):
    headers, _, _ = vault
    def unavailable(_):
        raise ConnectionError('broker unavailable')
    monkeypatch.setattr(routes, 'embed_text', SimpleNamespace(delay=unavailable))
    response = await client.get('/api/images/smart-search?query=forest', headers=headers)
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_deleting_exact_keeper_promotes_survivor(client, vault, session_factory):
    headers, _, _ = vault
    ids = [(await upload(client, headers, name)).json()['items'][0]['image']['id']
           for name in ('original.png', 'copy.png', 'copy2.png')]
    response = await client.delete(f'/api/images/{ids[0]}?confirm=true', headers=headers)
    assert response.status_code == 200
    async with session_factory() as db:
        keeper = await db.get(Image, UUID(ids[1]))
        copy = await db.get(Image, UUID(ids[2]))
        assert keeper.exact_duplicate_of_id is None
        assert keeper.status.value != 'EXACT_DUPLICATE'
        assert copy.exact_duplicate_of_id == keeper.id
    assert (await client.get('/api/images?filter_by=exact', headers=headers)).json()['total'] == 1


@pytest.mark.asyncio
async def test_whitespace_display_name_rejected(client):
    response = await client.post('/api/auth/register', json={
        'email': 'blank@example.com', 'display_name': '  ', 'password': 'strong-password'})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_access_token_requires_expiry(client, vault):
    _, _, auth = vault
    settings = get_settings()
    token = jwt.encode({'sub': auth['user']['id'], 'type': 'access'},
                       settings.jwt_secret, algorithm=settings.jwt_algorithm)
    response = await client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_storage_outage_defers_cleanup_without_dangling_images(client, vault, session_factory, monkeypatch):
    from app.models import ObjectDeletion
    from app.services.cleanup import purge_objects
    headers, fake, _ = vault
    image_id = (await upload(client, headers)).json()['items'][0]['image']['id']
    delete = fake.delete
    monkeypatch.setattr(fake, 'delete', lambda _: (_ for _ in ()).throw(ConnectionError('offline')))
    response = await client.post('/api/images/bulk-delete', headers=headers,
                                 json={'image_ids': [image_id], 'confirm': True})
    assert response.status_code == 200
    assert response.json()['cleanup_pending'] == 2
    assert len(fake.objects) == 1
    assert (await client.get('/api/images', headers=headers)).json()['total'] == 0
    async with session_factory() as db:
        records = list((await db.scalars(select(ObjectDeletion))).all())
        assert len(records) == 2 and all(row.attempts == 1 for row in records)
    monkeypatch.setattr(fake, 'delete', delete)
    async with session_factory() as db:
        assert await purge_objects(db, fake) == 0
        assert not (await db.scalars(select(ObjectDeletion))).all()
    assert not fake.objects


@pytest.mark.asyncio
async def test_failed_deletion_commit_never_removes_storage(client, vault, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    headers, fake, _ = vault
    image_id = (await upload(client, headers)).json()['items'][0]['image']['id']
    commit = AsyncSession.commit
    async def fail_commit(_):
        raise RuntimeError('database commit failed')
    monkeypatch.setattr(AsyncSession, 'commit', fail_commit)
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test') as http:
        response = await http.delete(f'/api/images/{image_id}?confirm=true', headers=headers)
    assert response.status_code == 500
    assert len(fake.objects) == 1
    monkeypatch.setattr(AsyncSession, 'commit', commit)
    assert (await client.get(f'/api/images/{image_id}', headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_invalid_second_file_rolls_back_entire_upload(client, vault):
    headers, fake, _ = vault
    response = await client.post('/api/images/upload', headers=headers, files=[
        ('files', ('valid.png', png_bytes(), 'image/png')),
        ('files', ('bad.png', b'not an image', 'image/png')),
    ])
    assert response.status_code == 400
    assert not fake.objects
    assert (await client.get('/api/images', headers=headers)).json()['total'] == 0


@pytest.mark.asyncio
async def test_reindex_does_not_publish_an_active_exact_copy_twice(client, vault, monkeypatch):
    headers, _, _ = vault
    await upload(client, headers)
    await upload(client, headers, 'copy.png')
    queued = []
    monkeypatch.setattr(routes, 'process_image', SimpleNamespace(delay=queued.append))
    response = await client.post('/api/images/reindex?missing_only=false', headers=headers)
    assert response.json()['queued'] == 0
    assert queued == []


@pytest.mark.asyncio
async def test_reindex_reports_publish_failures(client, vault, session_factory, monkeypatch):
    from app.models import JobStatus, ProcessingStatus
    headers, _, _ = vault
    image_id = (await upload(client, headers)).json()['items'][0]['image']['id']
    async with session_factory() as db:
        image = await db.get(Image, UUID(image_id))
        image.status = ProcessingStatus.FAILED
        job = await db.scalar(select(ProcessingJob))
        job.status = JobStatus.FAILED
        await db.commit()
    monkeypatch.setattr(routes, 'process_image', SimpleNamespace(delay=lambda _: (_ for _ in ()).throw(ConnectionError('offline'))))
    response = await client.post('/api/images/reindex', headers=headers)
    assert response.json()['queued'] == 0
    assert response.json()['failed'] == 1
    assert 'retry' in response.json()['message'].lower()


@pytest.mark.asyncio
async def test_upload_config_matches_server_limits_and_requires_auth(client, vault, monkeypatch):
    headers, _, _ = vault
    monkeypatch.setattr(get_settings(), 'max_batch_files', 10)
    monkeypatch.setattr(get_settings(), 'max_video_upload_bytes', 100 * 1024 * 1024)
    response = await client.get('/api/images/config', headers=headers)
    assert response.status_code == 200
    assert response.json()['max_batch_files'] == 10
    assert response.json()['max_video_upload_bytes'] == 100 * 1024 * 1024
    assert '.jpeg' in response.json()['allowed_extensions']
    assert (await client.get('/api/images/config')).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('query', ['%20%20', '%09%20', 'a%20'])
async def test_semantic_search_rejects_blank_or_single_character_query(client, vault, query):
    headers, _, _ = vault
    assert (await client.get(f'/api/images/smart-search?query={query}', headers=headers)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize('old_status,old_version', [('READY', 5), ('FAILED', 6), ('PENDING', 6)])
async def test_stale_matches_are_hidden_consistently(client, vault, session_factory, old_status, old_version):
    from app.models import DuplicateMatch, DuplicateType, ProcessingStatus
    headers, _, auth = vault
    ids = [(await upload(client, headers, name, png_bytes(color))).json()['items'][0]['image']['id']
           for name, color in [('first.png',(10,80,30)), ('second.png',(40,10,90))]]
    async with session_factory() as db:
        first, second = [await db.get(Image, UUID(value)) for value in ids]
        first.status = ProcessingStatus(old_status)
        first.analysis_version = old_version
        second.status = ProcessingStatus.READY
        second.analysis_version = 6
        db.add(DuplicateMatch(user_id=UUID(auth['user']['id']), source_image_id=first.id,
                              target_image_id=second.id, match_type=DuplicateType.PERCEPTUAL,
                              similarity_score=0.98))
        await db.commit()
    listed = (await client.get('/api/images', headers=headers)).json()
    assert all(item['best_similarity'] is None for item in listed['items'])
    assert (await client.get('/api/images?filter_by=similar', headers=headers)).json()['total'] == 0
    assert not (await client.get(f'/api/images/{ids[1]}/similar', headers=headers)).json()
    assert not (await client.get(f'/api/images/{ids[1]}', headers=headers)).json()['similar_images']
    assert (await client.get('/api/dashboard', headers=headers)).json()['similar_images'] == 0
    assert (await client.get('/api/duplicates/review', headers=headers)).json()['total_groups'] == 0


@pytest.mark.asyncio
async def test_delete_during_processing_cleans_recreated_thumbnail(session_factory, monkeypatch):
    from uuid import uuid4
    from app.models import ObjectDeletion, User, ProcessingStatus
    from app.services.intelligence import OcrResult
    from app.worker import tasks
    from app.services.cleanup import purge_objects
    fake = FakeStorage()
    image_id = uuid4()
    fake.objects['original'] = png_bytes()
    fake.get_bytes = lambda key: fake.objects[key]
    async with session_factory() as db:
        user = User(email='race@example.com', display_name='Test', password_hash='unused')
        db.add(user)
        await db.flush()
        db.add(Image(id=image_id, user_id=user.id, original_filename='race.png', object_key='original',
                     thumbnail_key='thumb', mime_type='image/png', file_size=len(png_bytes()),
                     sha256='a'*64, status=ProcessingStatus.PENDING))
        await db.commit()
    monkeypatch.setattr(tasks, 'SessionLocal', session_factory)
    monkeypatch.setattr(tasks, 'storage', fake)
    monkeypatch.setattr(tasks, 'embedder', SimpleNamespace(image_embedding_frames=lambda _: (None,0,'fixture')))
    monkeypatch.setattr(tasks, 'extract_ocr_layout', lambda _: OcrResult('',None,[],None))
    monkeypatch.setattr(tasks.face_engine, 'analyze', lambda _: [])
    save = tasks._save_result
    async def delete_before_save(*args, **kwargs):
        async with session_factory() as db:
            image = await db.get(Image, image_id)
            await db.delete(image)
            await db.commit()
        fake.delete('original')
        fake.delete('thumb')
        fake.put_bytes('thumb', b'recreated thumbnail', 'image/webp')
        return await save(*args, **kwargs)
    monkeypatch.setattr(tasks, '_save_result', delete_before_save)
    result = await tasks._process(image_id)
    assert result['status'] == 'missing'
    async with session_factory() as db:
        assert len((await db.scalars(select(ObjectDeletion))).all()) == 2
        await purge_objects(db, fake)
    assert not fake.objects


@pytest.mark.asyncio
async def test_exact_copy_analysis_is_counted_and_polled(client, vault, session_factory):
    from datetime import UTC, datetime
    from app.models import JobStatus, ProcessingStatus
    headers, _, _ = vault
    original_id = (await upload(client, headers)).json()['items'][0]['image']['id']
    async with session_factory() as db:
        original = await db.get(Image, UUID(original_id))
        original.status = ProcessingStatus.READY
        original.processed_at = datetime.now(UTC)
        job = await db.scalar(select(ProcessingJob))
        job.status = JobStatus.COMPLETE
        await db.commit()
    copy = (await upload(client, headers, 'copy.png')).json()['items'][0]['image']
    assert copy['status'] == 'EXACT_DUPLICATE'
    assert copy['analysis_pending'] is True
    report = (await client.get('/api/duplicates/review', headers=headers)).json()
    assert report['processing_images'] == 1
    detail = (await client.get(f"/api/images/{copy['id']}", headers=headers)).json()
    assert detail['analysis_pending'] is True


@pytest.mark.asyncio
async def test_rollback_cleanup_survives_a_storage_outage(client, vault, session_factory, monkeypatch):
    from app.models import ObjectDeletion
    from app.services.cleanup import purge_objects
    headers, fake, _ = vault
    real_delete = fake.delete
    monkeypatch.setattr(fake, 'delete', lambda _: (_ for _ in ()).throw(ConnectionError('offline')))
    response = await client.post('/api/images/upload', headers=headers, files=[
        ('files', ('valid.png', png_bytes(), 'image/png')),
        ('files', ('invalid.png', b'bad', 'image/png')),
    ])
    assert response.status_code == 400
    assert (await client.get('/api/images', headers=headers)).json()['total'] == 0
    async with session_factory() as db:
        assert len((await db.scalars(select(ObjectDeletion))).all()) == 1
    monkeypatch.setattr(fake, 'delete', real_delete)
    async with session_factory() as db:
        await purge_objects(db, fake)
    assert not fake.objects
