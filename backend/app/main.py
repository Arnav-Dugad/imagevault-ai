import time
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api import albums, analytics, auth, health, images
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.services.storage import storage

settings = get_settings()
configure_logging(settings.debug)
logger = structlog.get_logger("imagevault.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        storage.ensure_bucket()
        logger.info("object_storage_ready", bucket=settings.minio_bucket)
    except Exception as exc:
        logger.warning("object_storage_startup_failed", error=str(exc))
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Self-hosted private-cloud image storage with SHA-256 duplicate detection, "
        "local OpenCLIP similarity, pgvector search, and observable asynchronous processing."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = time.perf_counter()
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed", method=request.method, path=request.url.path)
            raise
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    duration = time.perf_counter() - started
    HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
    HTTP_LATENCY.labels(request.method, path).observe(duration)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    logger.info(
        "request_complete",
        method=request.method,
        path=path,
        status=response.status_code,
        duration_ms=round(duration * 1000, 2),
    )
    return response


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(images.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)
app.include_router(albums.router, prefix=settings.api_prefix)
