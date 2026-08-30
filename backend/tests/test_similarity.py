import math

import pytest

from app.services.images import similarity_classification
from app.worker.embedder import normalize_vector
from app.worker.tasks import _phash_distance, _thumbnail_and_metadata


def test_normalize_vector_produces_unit_length():
    vector = normalize_vector([3.0, 4.0])
    assert vector == pytest.approx([0.6, 0.8])
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)


def test_similarity_labels_are_explicit_and_configurable():
    assert similarity_classification(0.97) == "Very Similar"
    assert similarity_classification(0.90) == "Similar"
    assert similarity_classification(0.80) == "Possibly Related"


def test_perceptual_hash_distance():
    assert _phash_distance("0000000000000000", "0000000000000000") == 0
    assert _phash_distance("0000000000000000", "ffffffffffffffff") == 64


def test_thumbnail_pipeline_generates_webp_metadata():
    from tests.test_images import png_bytes

    thumbnail, width, height, perceptual_hash, _, _ = _thumbnail_and_metadata(png_bytes())
    assert thumbnail.startswith(b"RIFF")
    assert (width, height) == (32, 24)
    assert len(perceptual_hash) == 16
