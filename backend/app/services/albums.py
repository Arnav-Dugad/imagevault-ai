from collections.abc import Iterable
from datetime import datetime, timedelta
from uuid import UUID

from app.models import Image
from app.services.similarity import cosine_similarity

FaceVector = tuple[UUID, UUID, list[float], float]


def image_time(image: Image) -> datetime:
    return image.exif_timestamp or image.created_at


def connected_components(nodes: Iterable[UUID], edges: Iterable[tuple[UUID, UUID]]) -> list[list[UUID]]:
    node_list = list(dict.fromkeys(nodes))
    parent = {node: node for node in node_list}

    def find(node: UUID) -> UUID:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(first: UUID, second: UUID) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parent[second_root] = first_root

    for first, second in edges:
        if first in parent and second in parent:
            union(first, second)
    groups: dict[UUID, list[UUID]] = {}
    for node in node_list:
        groups.setdefault(find(node), []).append(node)
    return list(groups.values())


def group_events(
    images: list[Image],
    visual_edges: set[frozenset[UUID]],
    *,
    gap_hours: int,
) -> list[list[Image]]:
    ordered = sorted(images, key=image_time)
    if not ordered:
        return []
    groups: list[list[Image]] = [[ordered[0]]]
    for image in ordered[1:]:
        group = groups[-1]
        previous = group[-1]
        gap = image_time(image) - image_time(previous)
        same_camera = bool(image.camera_model and image.camera_model == previous.camera_model)
        visually_connected = any(
            frozenset((image.id, member.id)) in visual_edges for member in group[-8:]
        )
        if gap <= timedelta(hours=3) or (
            gap <= timedelta(hours=gap_hours) and (same_camera or visually_connected)
        ):
            group.append(image)
        else:
            groups.append([image])
    return sorted(groups, key=lambda group: image_time(group[-1]), reverse=True)


def group_bursts(
    images: list[Image],
    visual_edges: set[frozenset[UUID]],
    *,
    gap_seconds: int,
) -> list[list[Image]]:
    image_map = {image.id: image for image in images}
    burst_edges: list[tuple[UUID, UUID]] = []
    for edge in visual_edges:
        if len(edge) != 2:
            continue
        first_id, second_id = tuple(edge)
        first, second = image_map.get(first_id), image_map.get(second_id)
        if first is None or second is None:
            continue
        gap = abs((image_time(first) - image_time(second)).total_seconds())
        if gap <= gap_seconds:
            burst_edges.append((first_id, second_id))
    groups = connected_components(image_map, burst_edges)
    bursts = [
        sorted((image_map[image_id] for image_id in group), key=image_time)
        for group in groups
        if len(group) >= 2
    ]
    return sorted(bursts, key=lambda group: image_time(group[-1]), reverse=True)


def _normalized(values: list[float]) -> list[float]:
    magnitude = sum(value * value for value in values) ** 0.5
    if magnitude <= 1e-12:
        return []
    return [value / magnitude for value in values]


def _centroid(cluster: list[FaceVector]) -> list[float]:
    dimensions = len(cluster[0][2])
    averaged = [
        sum(face[2][index] * max(0.35, face[3]) for face in cluster)
        / sum(max(0.35, face[3]) for face in cluster)
        for index in range(dimensions)
    ]
    return _normalized(averaged)


def cluster_face_records(faces: list[FaceVector], threshold: float) -> list[list[FaceVector]]:
    """Agglomerative identity clustering without single-link chain errors.

    Every merge must pass centroid, average-link, and strongest-pair checks.
    This still permits cross-pose matches near SFace's published threshold but
    prevents one ambiguous face from joining two otherwise distinct people.
    """
    prepared = [
        (face_id, image_id, normalized, confidence)
        for face_id, image_id, embedding, confidence in faces
        if (normalized := _normalized(embedding))
    ]
    clusters: list[list[FaceVector]] = [[face] for face in prepared]
    while True:
        best: tuple[float, int, int] | None = None
        for first_index, first in enumerate(clusters):
            first_images = {face[1] for face in first}
            first_centroid = _centroid(first)
            for second_index in range(first_index + 1, len(clusters)):
                second = clusters[second_index]
                if first_images.intersection(face[1] for face in second):
                    continue
                cross_scores = [
                    cosine_similarity(first_face[2], second_face[2])
                    for first_face in first
                    for second_face in second
                ]
                average = sum(cross_scores) / len(cross_scores)
                strongest = max(cross_scores)
                centroid_score = cosine_similarity(first_centroid, _centroid(second))
                average_floor = threshold - (0.025 if len(first) + len(second) >= 4 else 0.012)
                if (
                    centroid_score < threshold
                    or average < average_floor
                    or strongest < threshold
                ):
                    continue
                merge_score = centroid_score * 0.58 + average * 0.32 + strongest * 0.10
                if best is None or merge_score > best[0]:
                    best = (merge_score, first_index, second_index)
        if best is None:
            break
        _, first_index, second_index = best
        clusters[first_index].extend(clusters.pop(second_index))

    return sorted(
        clusters,
        key=lambda cluster: (-len({face[1] for face in cluster}), str(cluster[0][0])),
    )


def cluster_faces(
    faces: list[tuple[UUID, UUID, list[float]]], threshold: float
) -> list[list[UUID]]:
    clusters = cluster_face_records(
        [(face_id, image_id, embedding, 1.0) for face_id, image_id, embedding in faces],
        threshold,
    )
    return [list(dict.fromkeys(face[1] for face in cluster)) for cluster in clusters]


def best_photo(images: list[Image]) -> Image:
    return max(
        images,
        key=lambda image: (
            image.quality_score or 0,
            image.blur_score or 0,
            (image.width or 0) * (image.height or 0),
            -image.file_size,
        ),
    )
