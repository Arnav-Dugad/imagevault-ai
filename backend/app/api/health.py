from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import func, select, text

from app.api.dependencies import CurrentUser, Database
from app.core.config import get_settings
from app.models import JobStatus, ProcessingJob
from app.metrics import WORKER_QUEUE_SIZE
from app.schemas import ComponentHealth, SystemStatusResponse
from app.services.storage import storage

router = APIRouter(tags=["Health"])
settings = get_settings()


async def component_status(db: Database) -> tuple[dict[str, ComponentHealth], int, int | None]:
    components: dict[str, ComponentHealth] = {}
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = ComponentHealth(status="healthy", detail="Connected")
    except Exception:
        components["database"] = ComponentHealth(status="unhealthy", detail="Connection failed")

    try:
        healthy = storage.healthy()
        components["object_storage"] = ComponentHealth(
            status="healthy" if healthy else "unhealthy",
            detail="MinIO bucket available" if healthy else "Bucket unavailable",
        )
    except Exception:
        components["object_storage"] = ComponentHealth(status="unhealthy", detail="Connection failed")

    try:
        pending = int(
            await db.scalar(
                select(func.count()).select_from(ProcessingJob).where(
                    ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
                )
            )
            or 0
        )
    except Exception:
        pending = 0
    queue_size: int | None = None
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        heartbeat = await redis_client.get("imagevault:worker:heartbeat")
        queue_size = int(await redis_client.llen("celery"))
        WORKER_QUEUE_SIZE.set(queue_size)
        components["worker"] = ComponentHealth(
            status="healthy" if heartbeat else "degraded",
            detail="Heartbeat received" if heartbeat else "No recent heartbeat",
        )
        model_status = await redis_client.get("imagevault:worker:model")
        model_device = await redis_client.get("imagevault:worker:device")
        components["embedding_model"] = ComponentHealth(
            status="healthy" if model_status == "loaded" else "idle",
            detail=(
                f"OpenCLIP loaded on {model_device or 'CPU'}"
                if model_status == "loaded"
                else "Loads on first AI job"
            ),
        )
    except Exception:
        components["worker"] = ComponentHealth(status="unhealthy", detail="Redis unavailable")
        components["embedding_model"] = ComponentHealth(status="unknown")
    finally:
        await redis_client.aclose()
    return components, pending, queue_size


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health")
@router.get("/health/ready")
async def ready(response: Response, db: Database) -> dict[str, object]:
    components, _, _ = await component_status(db)
    required = [components["database"].status, components["object_storage"].status]
    healthy = all(item == "healthy" for item in required)
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if healthy else "unhealthy",
        "database": components["database"].status,
        "objectStorage": components["object_storage"].status,
        "worker": components["worker"].status,
    }


@router.get("/api/system/status", response_model=SystemStatusResponse, tags=["System"])
async def system_status(_: CurrentUser, db: Database) -> SystemStatusResponse:
    components, pending, queue_size = await component_status(db)
    overall = "healthy" if all(
        components[key].status == "healthy" for key in ("database", "object_storage")
    ) else "degraded"
    return SystemStatusResponse(
        status=overall,
        version=settings.app_version,
        api=ComponentHealth(status="healthy", detail="FastAPI responding"),
        database=components["database"],
        object_storage=components["object_storage"],
        worker=components["worker"],
        embedding_model=components["embedding_model"],
        pending_jobs=pending,
        queue_size=queue_size,
    )
