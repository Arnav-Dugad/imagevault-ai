from datetime import UTC, datetime, timedelta
from uuid import uuid4

from PIL import Image as PillowImage, ImageDraw, ImageFilter

from app.models import Image, ProcessingStatus
from app.services.albums import (
    best_photo,
    cluster_face_records,
    cluster_faces,
    group_bursts,
    group_events,
)
from app.services.intelligence import merge_smart_labels, quality_metrics


def sample_image(*, created_at: datetime, quality: float = 0.5) -> Image:
    image_id = uuid4()
    return Image(
        id=image_id,
        user_id=uuid4(),
        original_filename=f"{image_id}.jpg",
        object_key=f"objects/{image_id}.jpg",
        thumbnail_key=f"thumbs/{image_id}.webp",
        mime_type="image/jpeg",
        file_size=1000,
        sha256="a" * 64,
        status=ProcessingStatus.READY,
        created_at=created_at,
        quality_score=quality,
    )


def test_quality_score_rewards_a_sharp_frame():
    sharp = PillowImage.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(sharp)
    for x in range(0, 1200, 40):
        draw.line((x, 0, x, 800), fill="black", width=6)
    for y in range(0, 800, 40):
        draw.line((0, y, 1200, y), fill="black", width=6)
    blurred = sharp.filter(ImageFilter.GaussianBlur(12))

    sharp_score = quality_metrics(sharp)
    blurred_score = quality_metrics(blurred)

    assert sharp_score.blur > blurred_score.blur
    assert sharp_score.overall > blurred_score.overall


def test_tiny_compressed_looking_image_cannot_report_perfect_sharpness():
    tiny = PillowImage.new("RGB", (190, 265), "#d88f7e")
    draw = ImageDraw.Draw(tiny)
    draw.rectangle((42, 25, 146, 245), outline="black", width=2)
    draw.ellipse((66, 32, 126, 92), fill="#c88a72", outline="black", width=2)

    score = quality_metrics(tiny)

    assert score.blur < 0.65
    assert score.resolution < 0.05


def test_rule_labels_prioritize_receipts_and_people():
    labels = merge_smart_labels(
        {"product": 0.9},
        is_screenshot=False,
        ocr_text="Receipt subtotal tax total amount payment",
        face_boxes=[
            {"x": 10, "y": 10, "width": 80, "height": 80},
            {"x": 100, "y": 10, "width": 80, "height": 80},
        ],
        image_size=(300, 200),
    )
    assert labels[:2] == ["receipt", "people"]
    assert "product" in labels


def test_portrait_is_not_called_a_selfie_without_strong_evidence():
    labels = merge_smart_labels(
        {"selfie": 0.74, "product": 0.2},
        is_screenshot=False,
        ocr_text="2%",
        face_boxes=[{"x": 45, "y": 20, "width": 90, "height": 105}],
        image_size=(190, 265),
        filename="event-photo.jpeg",
    )

    assert "portrait" in labels
    assert "selfie" not in labels
    assert "document" not in labels


def test_events_and_bursts_require_the_right_relationships():
    start = datetime(2026, 8, 30, 10, tzinfo=UTC)
    first = sample_image(created_at=start, quality=0.4)
    second = sample_image(created_at=start + timedelta(seconds=5), quality=0.9)
    later = sample_image(created_at=start + timedelta(days=2), quality=0.7)
    visual_edges = {frozenset((first.id, second.id))}

    events = group_events([later, second, first], visual_edges, gap_hours=12)
    bursts = group_bursts([first, second, later], visual_edges, gap_seconds=12)

    assert [len(group) for group in events] == [1, 2]
    assert bursts == [[first, second]]
    assert best_photo(bursts[0]) is second


def test_face_clustering_is_conservative_and_deduplicates_images():
    first_face, second_face, third_face = uuid4(), uuid4(), uuid4()
    first_image, second_image, third_image = uuid4(), uuid4(), uuid4()
    vector = [1.0, 0.0, 0.0]
    groups = cluster_faces(
        [
            (first_face, first_image, vector),
            (second_face, second_image, [0.99, 0.01, 0.0]),
            (third_face, third_image, [0.0, 1.0, 0.0]),
        ],
        threshold=0.95,
    )
    assert groups[0] == [first_image, second_image]
    assert groups[1] == [third_image]


def test_face_clustering_does_not_chain_two_people_through_one_ambiguous_face():
    images = [uuid4(), uuid4(), uuid4()]
    faces = [
        (uuid4(), images[0], [1.0, 0.0], 1.0),
        (uuid4(), images[1], [0.8, 0.6], 1.0),
        (uuid4(), images[2], [0.28, 0.96], 1.0),
    ]

    groups = cluster_face_records(faces, threshold=0.79)

    assert sorted(len(group) for group in groups) == [1, 2]
