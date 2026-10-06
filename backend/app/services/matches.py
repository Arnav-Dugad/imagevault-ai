"""Only expose visual evidence from completed, current analyses."""
from sqlalchemy import exists, select
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.models import DuplicateMatch, Image, ProcessingStatus


def current_match_predicates():
    source, target = aliased(Image), aliased(Image)
    def current(image, key):
        return exists(select(image.id).where(
            image.id == key, image.user_id == DuplicateMatch.user_id,
            image.analysis_version >= get_settings().analysis_version,
            image.status.in_([ProcessingStatus.READY, ProcessingStatus.EXACT_DUPLICATE]),
        ))
    return current(source, DuplicateMatch.source_image_id), current(target, DuplicateMatch.target_image_id)
