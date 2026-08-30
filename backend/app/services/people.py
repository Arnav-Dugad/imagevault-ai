from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DetectedFace,
    FaceAssignment,
    FaceFeedback,
    FaceFeedbackType,
    Person,
)
from app.services.albums import FaceVector, cluster_face_records


@dataclass(frozen=True)
class PersonCluster:
    person: Person
    faces: list[FaceVector]


def learned_face_threshold(base: float, feedback: list[tuple[FaceFeedbackType, float]]) -> float:
    same = sorted(score for kind, score in feedback if kind == FaceFeedbackType.SAME)
    different = sorted(score for kind, score in feedback if kind == FaceFeedbackType.DIFFERENT)
    if same and different and different[-1] < same[0]:
        return round(max(0.22, min(0.42, (different[-1] + same[0]) / 2)), 4)
    if same and not different:
        return round(max(0.22, min(base, same[0] - 0.018)), 4)
    if different and not same:
        return round(min(0.42, max(base, different[-1] + 0.018)), 4)
    return base


async def reconcile_people(
    user_id: UUID,
    db: AsyncSession,
    *,
    embedding_model: str,
    base_threshold: float,
) -> tuple[list[PersonCluster], float]:
    faces = list(
        (
            await db.scalars(
                select(DetectedFace).where(
                    DetectedFace.user_id == user_id,
                    DetectedFace.embedding_model == embedding_model,
                    DetectedFace.confidence >= 0.42,
                )
            )
        ).all()
    )
    if not faces:
        return [], base_threshold
    face_ids = {face.id for face in faces}
    people = list((await db.scalars(select(Person).where(Person.user_id == user_id))).all())
    people_by_id = {person.id: person for person in people}
    assignments = list(
        (
            await db.scalars(
                select(FaceAssignment).where(
                    FaceAssignment.user_id == user_id,
                    FaceAssignment.face_id.in_(face_ids),
                )
            )
        ).all()
    )
    assignment_by_face = {assignment.face_id: assignment for assignment in assignments}
    seed_person_by_face = {
        assignment.face_id: assignment.person_id
        for assignment in assignments
        if assignment.source != "automatic"
        or bool(
            people_by_id.get(assignment.person_id)
            and people_by_id[assignment.person_id].confirmed
        )
    }
    feedback = list(
        (await db.scalars(select(FaceFeedback).where(FaceFeedback.user_id == user_id))).all()
    )
    threshold = learned_face_threshold(
        base_threshold,
        [(item.feedback_type, item.similarity_score) for item in feedback],
    )
    blocked = {
        frozenset((item.first_face_id, item.second_face_id))
        for item in feedback
        if item.feedback_type == FaceFeedbackType.DIFFERENT
    }
    records: list[FaceVector] = [
        (face.id, face.image_id, list(face.embedding), face.confidence) for face in faces
    ]
    groups = cluster_face_records(
        records,
        threshold,
        seed_person_by_face=seed_person_by_face,
        blocked_pairs=blocked,
    )

    old_auto_person = {
        assignment.face_id: assignment.person_id
        for assignment in assignments
        if assignment.source == "automatic"
    }
    used_people: set[UUID] = set()
    kept_faces: set[UUID] = set()
    result: list[PersonCluster] = []
    for group in groups:
        unique_images = {face[1] for face in group}
        seeded_people = {
            seed_person_by_face[face[0]] for face in group if face[0] in seed_person_by_face
        }
        confirmed_seed = any(
            people_by_id.get(person_id) and people_by_id[person_id].confirmed
            for person_id in seeded_people
        )
        if len(unique_images) < 2 and not confirmed_seed:
            continue
        person: Person | None = None
        if seeded_people:
            person = people_by_id.get(next(iter(seeded_people)))
        if person is None:
            overlap = Counter(
                old_auto_person[face[0]]
                for face in group
                if face[0] in old_auto_person and old_auto_person[face[0]] not in used_people
            )
            if overlap:
                person = people_by_id.get(overlap.most_common(1)[0][0])
        if person is None:
            person = Person(user_id=user_id)
            db.add(person)
            await db.flush()
            people_by_id[person.id] = person
        used_people.add(person.id)
        for face_id, _, _, confidence in group:
            assignment = assignment_by_face.get(face_id)
            if assignment is None:
                assignment = FaceAssignment(
                    user_id=user_id,
                    person_id=person.id,
                    face_id=face_id,
                    source="automatic",
                    confidence=confidence,
                )
                db.add(assignment)
                assignment_by_face[face_id] = assignment
            elif assignment.source == "automatic":
                assignment.person_id = person.id
                assignment.confidence = confidence
            kept_faces.add(face_id)
        result.append(PersonCluster(person, group))

    for assignment in assignments:
        if assignment.source == "automatic" and assignment.face_id not in kept_faces:
            await db.delete(assignment)
    for person in people:
        if not person.confirmed and person.id not in used_people:
            await db.delete(person)
    await db.commit()
    return result, threshold
