import math

import pytest

from app.services.images import similarity_classification
from app.services.similarity import evaluate_similarity, perceptual_similarity
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

    thumbnail, width, height, perceptual_hash, dhash, whash, color, _, _ = (
        _thumbnail_and_metadata(png_bytes())
    )
    assert thumbnail.startswith(b"RIFF")
    assert (width, height) == (32, 24)
    assert len(perceptual_hash) == 16
    assert len(dhash) == 16
    assert len(whash) == 16
    assert len(color) == 24


def test_multi_hash_similarity_rewards_consensus():
    score, distance = perceptual_similarity(
        ("0000000000000000", "0f0f0f0f0f0f0f0f", "3333333333333333"),
        ("0000000000000000", "0f0f0f0f0f0f0f0f", "3333333333333333"),
    )
    assert score == 1.0
    assert distance == 0


def test_similarity_engine_explains_near_duplicate_match():
    evidence = evaluate_similarity(
        first_hashes=("0000000000000000",) * 3,
        second_hashes=("0000000000000001",) * 3,
        first_color=[0.125] * 24,
        second_color=[0.125] * 24,
        first_size=(1600, 900),
        second_size=(1280, 720),
        clip_score=0.88,
        perceptual_hash_threshold=8,
        visual_similarity_threshold=0.85,
    )
    assert evidence is not None
    assert evidence.match_type == "PERCEPTUAL"
    assert evidence.score > 0.9
    assert "Near-identical visual fingerprint" in evidence.reasons


def test_similarity_engine_rejects_weak_single_signal():
    evidence = evaluate_similarity(
        first_hashes=("0000000000000000",) * 3,
        second_hashes=("ffffffffffffffff",) * 3,
        first_color=[1.0, 0.0] * 12,
        second_color=[0.0, 1.0] * 12,
        first_size=(1600, 900),
        second_size=(900, 1600),
        clip_score=0.60,
        perceptual_hash_threshold=8,
        visual_similarity_threshold=0.85,
    )
    assert evidence is None
