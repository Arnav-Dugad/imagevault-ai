"""Transactional deletion records survive storage outages and API restarts."""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import ObjectDeletion

logger = logging.getLogger(__name__)


async def purge_objects(db: AsyncSession, provider, *, keys: list[str] | None = None) -> int:
    query = select(ObjectDeletion).order_by(ObjectDeletion.attempts, ObjectDeletion.created_at)
    if keys is not None:
        if not keys:
            return 0
        query = query.where(ObjectDeletion.object_key.in_(keys))
    else:
        query = query.limit(50)
    records = list((await db.scalars(query.with_for_update(skip_locked=True))).all())
    pending = 0
    for record in records:
        try:
            await asyncio.to_thread(provider.delete, record.object_key)
        except Exception:
            logger.exception('Object cleanup deferred', extra={'object_key': record.object_key})
            record.attempts += 1
            record.error_message = 'Storage unavailable; cleanup will retry'
            pending += 1
        else:
            await db.delete(record)
    await db.commit()
    return pending


async def cleanup_loop(provider) -> None:
    while True:
        try:
            async with SessionLocal() as db:
                await purge_objects(db, provider)
        except Exception:
            logger.exception('Object cleanup pass failed')
        await asyncio.sleep(30)
