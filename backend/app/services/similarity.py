import math
from dataclasses import dataclass

import imagehash


@dataclass(frozen=True)
class SimilarityEvidence:
    score: float
    match_type: str
    clip_score: float
    perceptual_score: float
    color_score: float
    aspect_score: float
    phash_distance: int | None
    reasons: list[str]


def hash_distance(first: str | None, second: str | None) -> int | None:
    if not first or not second:
        return None
    try:
        return imagehash.hex_to_hash(first) - imagehash.hex_to_hash(second)
    except ValueError:
        return None


def perceptual_similarity(
    first_hashes: tuple[str | None, str | None, str | None],
    second_hashes: tuple[str | None, str | None, str | None],
) -> tuple[float, int | None]:
    distances = [
        distance
        for distance in (
            hash_distance(first, second)
            for first, second in zip(first_hashes, second_hashes, strict=True)
        )
        if distance is not None
    ]
    if not distances:
        return 0.0, None
    # Unrelated 64-bit image hashes average around 32 different bits. Mapping
    # that baseline to zero makes this score much more useful than a raw
    # percentage, while three independent hashes reduce accidental matches.
    scores = [max(0.0, 1.0 - distance / 32.0) for distance in distances]
    return sum(scores) / len(scores), distances[0]


def color_similarity(first: list[float] | None, second: list[float] | None) -> float:
    if not first or not second or len(first) != len(second):
        return 0.0
    # Bhattacharyya similarity works well for normalized per-channel
    # histograms and is robust to JPEG compression and moderate resizing.
    channels = 3 if len(first) % 3 == 0 else 1
    return max(0.0, min(1.0, sum(math.sqrt(max(0.0, a * b)) for a, b in zip(first, second)) / channels))


def aspect_similarity(
    first_width: int | None,
    first_height: int | None,
    second_width: int | None,
    second_height: int | None,
) -> float:
    if not all((first_width, first_height, second_width, second_height)):
        return 0.0
    first_ratio = float(first_width) / float(first_height)
    second_ratio = float(second_width) / float(second_height)
    return math.exp(-2.2 * abs(math.log(first_ratio / second_ratio)))


def cosine_similarity(first: list[float] | None, second: list[float] | None) -> float:
    if not first or not second or len(first) != len(second):
        return 0.0
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(first, second))))


def evaluate_similarity(
    *,
    first_hashes: tuple[str | None, str | None, str | None],
    second_hashes: tuple[str | None, str | None, str | None],
    first_color: list[float] | None,
    second_color: list[float] | None,
    first_size: tuple[int | None, int | None],
    second_size: tuple[int | None, int | None],
    clip_score: float,
    perceptual_hash_threshold: int,
    visual_similarity_threshold: float,
) -> SimilarityEvidence | None:
    perceptual, phash_distance = perceptual_similarity(first_hashes, second_hashes)
    color = color_similarity(first_color, second_color)
    aspect = aspect_similarity(*first_size, *second_size)
    clip = max(-1.0, min(1.0, clip_score))

    closest_hash_distance = min(
        (
            distance
            for distance in (
                hash_distance(first, second)
                for first, second in zip(first_hashes, second_hashes, strict=True)
            )
            if distance is not None
        ),
        default=65,
    )
    is_perceptual = (
        closest_hash_distance <= perceptual_hash_threshold
        and color >= 0.58
        and aspect >= 0.52
    ) or (perceptual >= 0.82 and color >= 0.68 and aspect >= 0.62)
    is_visual = clip >= visual_similarity_threshold
    if not is_perceptual and not is_visual:
        return None

    if is_perceptual:
        score = 0.55 * perceptual + 0.20 * max(0.0, clip) + 0.15 * color + 0.10 * aspect
        match_type = "PERCEPTUAL"
    else:
        score = 0.82 * max(0.0, clip) + 0.10 * color + 0.08 * aspect
        match_type = "VISUAL"

    reasons: list[str] = []
    if closest_hash_distance <= perceptual_hash_threshold:
        reasons.append("Near-identical visual fingerprint")
    elif perceptual >= 0.72:
        reasons.append("Strong structural resemblance")
    if clip >= max(0.90, visual_similarity_threshold):
        reasons.append("Very strong AI visual match")
    elif clip >= visual_similarity_threshold:
        reasons.append("AI recognized similar content")
    if color >= 0.90:
        reasons.append("Matching color composition")
    if aspect >= 0.94:
        reasons.append("Matching frame geometry")
    if not reasons:
        reasons.append("Multiple visual signals agree")

    return SimilarityEvidence(
        score=max(0.0, min(1.0, score)),
        match_type=match_type,
        clip_score=clip,
        perceptual_score=perceptual,
        color_score=color,
        aspect_score=aspect,
        phash_distance=phash_distance,
        reasons=reasons,
    )
