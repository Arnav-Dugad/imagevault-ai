from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import imagehash
import numpy as np
import pytest
from PIL import Image as PILImage, ImageDraw, ImageEnhance, ImageOps

from app.api.analytics import _duplicate_groups
from app.models import DuplicateMatch, DuplicateType, Image, MediaKind, ProcessingStatus, User
from app.services.similarity import cosine_similarity, evaluate_similarity
from app.services.verification import spatial_similarity
from app.worker import tasks
from tests.test_images import FakeStorage, png_bytes


def scene():
    image = PILImage.new('RGB', (512, 384), '#92b6d5')
    draw = ImageDraw.Draw(image)
    draw.polygon([(0, 300), (150, 80), (300, 300)], fill='#324f42')
    draw.rectangle((230, 130, 460, 330), fill='#bc7751')
    for x in range(245, 455, 35):
        for y in range(150, 315, 35):
            draw.rectangle((x, y, x + 18, y + 23), fill='#233142')
    draw.ellipse((350, 30, 420, 100), fill='#f5dd95')
    return image


def encoded(image, format='PNG', **options):
    output = BytesIO()
    image.save(output, format=format, **options)
    return output.getvalue()


def evidence(first, second, clip=0):
    def hashes(image):
        return tuple(str(fn(image)) for fn in (imagehash.phash, imagehash.dhash, imagehash.whash))
    return evaluate_similarity(
        first_hashes=hashes(first), second_hashes=hashes(second),
        first_color=tasks._color_signature(first), second_color=tasks._color_signature(second),
        first_size=first.size, second_size=second.size, clip_score=clip,
        perceptual_hash_threshold=8, visual_similarity_threshold=0.85,
        spatial_score=spatial_similarity(encoded(first), encoded(second)),
    )


@pytest.mark.parametrize('transformation', ['resize', 'jpeg', 'brightness'])
def test_real_pixels_confirm_common_copy_transformations(transformation):
    first = scene()
    if transformation == 'resize':
        second = first.resize((256, 192), PILImage.Resampling.LANCZOS)
    elif transformation == 'jpeg':
        second = PILImage.open(BytesIO(encoded(first, 'JPEG', quality=65))).convert('RGB')
    else:
        second = ImageEnhance.Brightness(first).enhance(1.08)
    result = evidence(first, second)
    assert result is not None and result.match_type == 'PERCEPTUAL'
    assert 'Aligned pixels verified at two scales' in result.reasons


def test_rearranged_scene_is_not_a_confirmed_duplicate():
    result = evidence(scene(), ImageOps.mirror(scene()), clip=0.97)
    assert result is not None and result.match_type == 'VISUAL'
    assert any('review before deleting' in reason for reason in result.reasons)


def test_blank_hash_collision_is_not_confirmed():
    result = evidence(PILImage.new('RGB', (512, 384), '#aa1111'), PILImage.new('RGB', (512, 384), '#bb1111'))
    assert result is None


def test_one_hash_and_semantic_score_cannot_confirm_duplicate():
    result = evaluate_similarity(
        first_hashes=('0000000000000000',) * 3,
        second_hashes=('0000000000000000', 'ffffffffffffffff', 'ffffffffffffffff'),
        first_color=[0.125] * 24, second_color=[0.125] * 24,
        first_size=(100, 100), second_size=(100, 100), clip_score=0.87,
        perceptual_hash_threshold=8, visual_similarity_threshold=0.85, spatial_score=1,
    )
    assert result is None


def test_missing_verification_cannot_confirm_duplicate():
    result = evaluate_similarity(
        first_hashes=('0123456789abcdef',) * 3, second_hashes=('0123456789abcdef',) * 3,
        first_color=[0.125] * 24, second_color=[0.125] * 24,
        first_size=(100, 100), second_size=(100, 100), clip_score=0,
        perceptual_hash_threshold=8, visual_similarity_threshold=0.85,
    )
    assert result is None


def test_cosine_accepts_pgvector_arrays_and_rejects_invalid_values():
    assert cosine_similarity(np.array([3., 4.]), np.array([6., 8.])) == pytest.approx(1)
    assert cosine_similarity([float('nan'), 1], [1, 1]) == 0
    assert cosine_similarity([0, 0], [1, 1]) == 0


@pytest.mark.asyncio
async def test_review_never_infers_a_match_through_a_chain(session_factory, monkeypatch):
    monkeypatch.setattr('app.services.images.storage', FakeStorage())
    async with session_factory() as db:
        user = User(email='chain@example.com', display_name='Test', password_hash='unused')
        db.add(user)
        await db.flush()
        images = [Image(user_id=user.id, original_filename=f'{n}.png', object_key=f'{n}.png',
                        mime_type='image/png', file_size=100 + n, sha256=str(n) * 64,
                        width=100, height=100, analysis_version=6, status=ProcessingStatus.READY)
                  for n in range(3)]
        db.add_all(images)
        await db.flush()
        for first, second in zip(images, images[1:]):
            source, target = sorted((first.id, second.id), key=str)
            db.add(DuplicateMatch(user_id=user.id, source_image_id=source, target_image_id=target,
                                  match_type=DuplicateType.PERCEPTUAL, similarity_score=0.96))
        await db.commit()
        groups, _ = await _duplicate_groups(user.id, db)
        assert len(groups) == 1
        assert len(groups[0].candidates) == 1
        assert not any('Connected through' in reason for candidate in groups[0].candidates for reason in candidate.reasons)


@pytest.mark.asyncio
async def test_semantic_and_enrichment_outages_preserve_fingerprint_processing(monkeypatch):
    image_id = uuid4()
    image = SimpleNamespace(object_key='photo', thumbnail_key='thumb', mime_type='image/png', original_filename='photo.png', exact_duplicate_of_id=None)
    async def running(_):
        return image
    result = {}
    async def save(_, **kwargs):
        result.update(kwargs)
        return 1
    def unavailable(*_):
        raise RuntimeError('model unavailable')
    storage = FakeStorage()
    storage.objects['photo'] = png_bytes()
    storage.get_bytes = lambda key: storage.objects[key]
    monkeypatch.setattr(tasks, '_set_running', running)
    monkeypatch.setattr(tasks, '_save_result', save)
    monkeypatch.setattr(tasks, 'storage', storage)
    monkeypatch.setattr(tasks.embedder, 'image_embedding_frames', unavailable)
    monkeypatch.setattr(tasks.face_engine, 'analyze', unavailable)
    monkeypatch.setattr(tasks, 'extract_ocr_layout', unavailable)
    monkeypatch.setattr(tasks, '_heartbeat', lambda: None)
    response = await tasks._process(image_id)
    assert response['status'] == 'complete'
    assert result['embedding'] is None
    assert result['perceptual_hash'] and result['thumbnail']
    assert len(result['warnings']) == 3
    assert result['media_kind'] == MediaKind.PHOTO


@pytest.mark.asyncio
async def test_worker_persists_verified_copy_without_clip(session_factory, monkeypatch):
    storage = FakeStorage()
    storage.get_bytes = lambda key: storage.objects[key]
    first, second = uuid4(), uuid4()
    storage.objects[str(first)] = encoded(scene())
    storage.objects[str(second)] = encoded(scene().resize((256, 192), PILImage.Resampling.LANCZOS))
    def unavailable(*_):
        raise RuntimeError('model unavailable')
    monkeypatch.setattr(tasks, 'storage', storage)
    monkeypatch.setattr(tasks, 'SessionLocal', session_factory)
    monkeypatch.setattr(tasks.embedder, 'image_embedding_frames', unavailable)
    monkeypatch.setattr(tasks.face_engine, 'analyze', unavailable)
    monkeypatch.setattr(tasks, 'extract_ocr_layout', unavailable)
    monkeypatch.setattr(tasks, '_heartbeat', lambda: None)
    async with session_factory() as db:
        user = User(email='fallback@example.com', display_name='Test', password_hash='unused')
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
    from sqlalchemy import select
    async with session_factory() as db:
        matches = list((await db.scalars(select(DuplicateMatch))).all())
        assert len(matches) == 1
        assert matches[0].match_type == DuplicateType.PERCEPTUAL
        assert matches[0].clip_score == 0
        for image_id in (first, second):
            image = await db.get(Image, image_id)
            assert image.status == ProcessingStatus.READY
            assert image.embedding is None and image.error_message
            assert image.analysis_version == 6


@pytest.mark.asyncio
async def test_all_byte_identical_copies_stay_in_one_family(session_factory, monkeypatch):
    monkeypatch.setattr('app.services.images.storage', FakeStorage())
    async with session_factory() as db:
        user = User(email='copies@example.com', display_name='Test', password_hash='unused')
        db.add(user)
        await db.flush()
        for n in range(3):
            db.add(Image(user_id=user.id, original_filename=f'{n}.png', object_key=f'{n}.png',
                         mime_type='image/png', file_size=100, sha256='a' * 64,
                         status=ProcessingStatus.EXACT_DUPLICATE if n else ProcessingStatus.READY))
        await db.commit()
        groups, _ = await _duplicate_groups(user.id, db)
        assert len(groups) == 1 and len(groups[0].candidates) == 2
        assert all(item.match_type == DuplicateType.EXACT for item in groups[0].candidates)


@pytest.mark.asyncio
async def test_exact_copy_reuses_analysis_and_does_not_run_models(session_factory, monkeypatch):
    from datetime import UTC, datetime
    from app.models import DetectedFace
    storage = FakeStorage()
    storage.get_bytes = lambda key: storage.objects[key]
    storage.objects['original-thumb'] = encoded(scene())
    original_id, copy_id = uuid4(), uuid4()
    monkeypatch.setattr(tasks, 'storage', storage)
    monkeypatch.setattr(tasks, 'SessionLocal', session_factory)
    monkeypatch.setattr(tasks, '_heartbeat', lambda: None)
    def must_not_run(*_):
        pytest.fail('An exact copy must not invoke a model again')
    monkeypatch.setattr(tasks.embedder, 'image_embedding_frames', must_not_run)
    async with session_factory() as db:
        user = User(email='reuse@example.com', display_name='Test', password_hash='unused')
        db.add(user)
        await db.flush()
        original = Image(id=original_id, user_id=user.id, original_filename='original.png',
                         object_key='original', thumbnail_key='original-thumb', mime_type='image/png',
                         file_size=100, sha256='b' * 64, status=ProcessingStatus.READY,
                         analysis_version=6, processed_at=datetime.now(UTC), width=512, height=384,
                         ocr_text='Original text', face_count=1, embedding=[1.] + [0.] * 511)
        copy = Image(id=copy_id, user_id=user.id, original_filename='copy.png', object_key='copy',
                     thumbnail_key='copy-thumb', mime_type='image/png', file_size=100,
                     sha256='b' * 64, status=ProcessingStatus.EXACT_DUPLICATE,
                     exact_duplicate_of_id=original_id)
        db.add_all([original, copy])
        await db.flush()
        db.add(DetectedFace(user_id=user.id, image_id=original_id, face_index=0,
                            bounding_box={'x': 1, 'y': 2, 'width': 30, 'height': 30},
                            embedding=[1.] + [0.] * 127, confidence=.99, embedding_model='test'))
        await db.commit()
    result = await tasks._process(copy_id)
    assert result['device'] == 'reused'
    assert storage.objects['copy-thumb'] == storage.objects['original-thumb']
    from sqlalchemy import select
    async with session_factory() as db:
        copy = await db.get(Image, copy_id)
        assert copy.ocr_text == 'Original text' and copy.analysis_version == 6
        faces = list((await db.scalars(select(DetectedFace).where(DetectedFace.image_id == copy_id))).all())
        assert len(faces) == 1 and faces[0].face_index == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('near_id_first', [True, False])
async def test_exact_equivalence_preserves_verified_near_copy_in_family(session_factory, monkeypatch, near_id_first):
    from datetime import UTC, datetime
    monkeypatch.setattr('app.services.images.storage', FakeStorage())
    async with session_factory() as db:
        user = User(email='equivalence@example.com', display_name='Test', password_hash='unused')
        db.add(user)
        await db.flush()
        ids = [UUID(int=n) for n in ([2, 3, 1] if near_id_first else [1, 2, 3])]
        images = [Image(id=ids[n], user_id=user.id, original_filename=f'{n}.png', object_key=f'{n}.png',
                        mime_type='image/png', file_size=100, sha256=('a' if n < 2 else 'b') * 64,
                        created_at=datetime(2026, 1, 1, tzinfo=UTC),
                        analysis_version=6, status=ProcessingStatus.READY) for n in range(3)]
        db.add_all(images)
        await db.flush()
        source, target = sorted((images[0].id, images[2].id), key=str)
        db.add(DuplicateMatch(user_id=user.id, source_image_id=source, target_image_id=target,
                              match_type=DuplicateType.PERCEPTUAL, similarity_score=.97))
        await db.commit()
        groups, _ = await _duplicate_groups(user.id, db)
        assert len(groups) == 1 and len(groups[0].candidates) == 2
        assert groups[0].original.id in {images[0].id, images[1].id}
        assert {candidate.match_type for candidate in groups[0].candidates} == {DuplicateType.EXACT, DuplicateType.PERCEPTUAL}


def test_exif_orientation_dimensions_match_exported_copy():
    from app.services.media import decode_media
    first = scene()
    exif = first.getexif()
    exif[274] = 6
    source = encoded(first, 'JPEG', exif=exif)
    decoded = decode_media(source, 'image/jpeg')
    assert (decoded.width, decoded.height) == (384, 512)
    normalized = encoded(decoded.primary)
    exported = decode_media(normalized, 'image/png')
    assert (exported.width, exported.height) == (decoded.width, decoded.height)
    result = evidence(decoded.primary, exported.primary)
    assert result is not None and result.match_type == 'PERCEPTUAL'
