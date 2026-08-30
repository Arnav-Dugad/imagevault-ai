from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "imagevault_http_requests_total",
    "HTTP requests handled by the API",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "imagevault_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
IMAGE_UPLOADS = Counter("imagevault_image_uploads_total", "Images accepted for upload")
UPLOADED_BYTES = Counter("imagevault_uploaded_bytes_total", "Image bytes accepted")
IMAGES_PROCESSED = Counter("imagevault_images_processed_total", "Images processed")
EXACT_DUPLICATES = Counter(
    "imagevault_exact_duplicates_total", "Exact duplicates detected by SHA-256"
)
SIMILAR_IMAGES = Counter(
    "imagevault_similar_images_total", "Visual or perceptual matches detected"
)
PROCESSING_FAILURES = Counter(
    "imagevault_processing_failures_total", "Asynchronous processing failures"
)
INFERENCE_DURATION = Histogram(
    "imagevault_ai_inference_duration_seconds",
    "Local embedding inference time",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
PROCESSING_DURATION = Histogram(
    "imagevault_processing_duration_seconds",
    "End-to-end image worker time",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
WORKER_QUEUE_SIZE = Gauge("imagevault_worker_queue_size", "Pending Celery jobs")
MODEL_LOADED = Gauge("imagevault_embedding_model_loaded", "Whether the CLIP model is loaded")
