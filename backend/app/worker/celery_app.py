from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "imagevault",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    broker_connection_timeout=3,
    redis_socket_connect_timeout=3,
    redis_socket_timeout=3,
    result_backend_transport_options={"retry_policy": {"timeout": 3}},
    task_publish_retry=False,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
)
