from collections.abc import Iterable
from datetime import datetime, timedelta
from uuid import UUID

from app.models import Image
from app.services.similarity import cosine_similarity


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


def cluster_faces(
    faces: list[tuple[UUID, UUID, list[float]]], threshold: float
) -> list[list[UUID]]:
    face_ids = [face_id for face_id, _, _ in faces]
    face_by_id = {face_id: (image_id, embedding) for face_id, image_id, embedding in faces}
    edges: list[tuple[UUID, UUID]] = []
    for index, (first_id, first_image_id, first_embedding) in enumerate(faces):
        for second_id, second_image_id, second_embedding in faces[index + 1 :]:
            if first_image_id == second_image_id:
                continue
            if cosine_similarity(first_embedding, second_embedding) >= threshold:
                edges.append((first_id, second_id))
    components = connected_components(face_ids, edges)
    image_groups: list[list[UUID]] = []
    for component in components:
        image_ids = list(dict.fromkeys(face_by_id[face_id][0] for face_id in component))
        image_groups.append(image_ids)
    return sorted(image_groups, key=lambda group: (-len(group), str(group[0])))


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
