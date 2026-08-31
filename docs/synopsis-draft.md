# ImageVault AI project synopsis

## Project title

**ImageVault AI — Intelligent Private-Cloud Media Storage, Duplicate Detection, Search, and Organization Platform**

## Student details

- Student name(s): `[To be supplied]`
- Registration number(s): `[To be supplied]`
- Programme / batch / semester: `[To be supplied]`
- Team number: `[To be supplied]`

## Supervisor details

- Supervisor name: `[To be supplied]`
- Department: `[To be supplied]`

## Synopsis / abstract

ImageVault AI is a self-hosted private-cloud platform for securely storing, searching, analyzing, and organizing personal media. It accepts batches of standard photographs, animated images, HEIC/HEIF files, common camera RAW formats, and videos. Originals are stored privately in S3-compatible MinIO object storage, while PostgreSQL stores account-scoped metadata, processing state, cryptographic hashes, quality measurements, OCR results, face information, and pgvector embeddings. SHA-256 identifies byte-identical files before a background Celery worker performs more expensive local analysis.

The intelligence pipeline combines pHash, dHash, wHash, color and geometry evidence, sampled-frame OpenCLIP embeddings, and pgvector cosine retrieval to identify exact copies, edited or recompressed near-duplicates, and semantically related media. Natural-language search allows queries such as “person wearing white near a car.” Local multilingual Tesseract OCR extracts searchable text and word-level layout from screenshots and documents. The system also calculates sharpness, exposure, resolution, screenshot readability, and overall quality scores; generates smart labels; selects the best photo from bursts; groups events; and builds private people albums using local YuNet face detection and SFace embeddings.

People albums are persistent and user-controlled. Users can rename, merge, split, ignore, or restore people and provide private “same person” or “different person” feedback. This feedback remains in the local database, preserves explicit identity decisions across re-analysis, and adapts the account’s clustering threshold. The system does not contact a public face-recognition service and does not attempt to discover real-world identities.

The project emphasizes Cloud Computing and DevOps as much as artificial intelligence. The React client, FastAPI API, Redis queue, Celery media worker, PostgreSQL/pgvector, MinIO, Nginx, Prometheus, and Grafana services are containerized with Docker. Docker Compose provides the primary laptop deployment, while Kubernetes on Minikube demonstrates orchestration, health probes, persistent volumes, configuration, secrets, resource controls, and horizontal API scaling. Terraform defines the local Kubernetes infrastructure, GitHub Actions validates changes, and Prometheus/Grafana provide metrics and operational dashboards. All required components use free/open-source software and no commercial AI API or paid public-cloud subscription is required.

## Problem statement

Personal media collections grow through phone cameras, messaging applications, screenshots, downloads, burst photography, edited exports, and repeated backups. This creates byte-identical duplicates, resized or recompressed copies, visually similar shots, weak or blurry photographs, and large collections that are difficult to search manually. Filename comparison is unreliable because identical files can have different names, while visually equivalent files can have different bytes. Important text inside screenshots and documents is also invisible to ordinary filename search.

Existing organization methods often separate duplicate cleanup, visual search, OCR, face grouping, quality review, and infrastructure monitoring into unrelated tools or external services. This can increase privacy exposure, operating cost, and management complexity. ImageVault AI addresses these problems with local media intelligence inside a reproducible private-cloud architecture. AI results are advisory, user corrections are retained, and deletion always requires explicit confirmation.

## Objectives

1. Build a secure, account-isolated private media vault using PostgreSQL and MinIO.
2. Detect byte-identical, perceptual, and visually related media using explainable multi-signal evidence.
3. Support natural-language search, multilingual OCR, document understanding, smart labels, and quality scoring without external AI APIs.
4. Organize collections into events, burst best-shots, and private user-correctable people albums.
5. Index photographs, animated images, HEIC/HEIF, camera RAW files, and representative video frames.
6. Process uploads asynchronously with automatic GPU use when supported and safe CPU fallback.
7. Demonstrate containerization, orchestration, infrastructure as code, CI/CD, monitoring, health checks, and structured logging.
8. Preserve user control through explainable results, guarded bulk actions, and no automatic deletion.

## Proposed solution and modules

1. **Authentication and isolation:** local registration/login, Argon2 password hashing, expiring JWT access, and ownership checks on every private query.
2. **Media intake and object storage:** signature and size validation, batch upload, UUID object keys, private MinIO originals, generated WebP thumbnails, and separate limits for photos and large media.
3. **Exact and visual duplicate intelligence:** SHA-256, three perceptual hashes, color histograms, frame geometry, multi-view/multi-frame OpenCLIP vectors, pgvector retrieval, connected duplicate families, and explainable confidence evidence.
4. **Search and local understanding:** filename search, natural-language semantic search, multilingual OCR, positioned word layout, document-type inference, and smart labels.
5. **Photo-quality intelligence:** sharpness, exposure, resolution, screenshot readability, overall quality, and burst best-photo selection.
6. **Private people intelligence:** local face detection/embedding, persistent albums, rename, merge, split, ignore/restore, and private same/different-person feedback learning.
7. **Smart albums:** automatic event albums using capture time and visual relationships, people albums, and burst groups with recommended keepers.
8. **Gallery and review experience:** responsive gallery, media details, video playback, OCR details, similarity evidence, multi-selection, guarded bulk deletion, animated navigation, and accessible validation feedback.
9. **Analytics and observability:** storage/savings/activity dashboards, health and readiness checks, queue/model state, structured logs, Prometheus metrics, and provisioned Grafana dashboards.
10. **Cloud and DevOps platform:** Docker Compose, Nginx gateway, Kubernetes/Minikube manifests, Terraform, GitHub Actions, persistent volumes, secrets, probes, resource limits, and optional scaling.

## Tools and technologies

| Classification | Technology |
|---|---|
| Private cloud / orchestration | Kubernetes, Minikube |
| Containerization | Docker, Docker Compose |
| Object storage | MinIO |
| Database / vector search | PostgreSQL 16, pgvector |
| Backend / asynchronous jobs | FastAPI, SQLAlchemy, Alembic, Celery, Redis |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Framer Motion |
| Visual AI | OpenCLIP, PyTorch, OpenCV YuNet and SFace |
| OCR / image processing | Tesseract OCR, Pillow, pillow-heif, ImageHash, rawpy/LibRaw |
| Video processing | FFmpeg, FFprobe |
| Infrastructure as Code | Terraform |
| CI/CD | GitHub Actions |
| Monitoring / visualization | Prometheus, Grafana OSS |
| Gateway | Nginx |
| Version control | Git, GitHub |

## System workflow

1. The authenticated user selects one or more supported media files.
2. The API validates content signatures and limits, generates private object keys, calculates SHA-256, and stores metadata and the original.
3. Exact byte matches are identified immediately; other media is queued through Redis.
4. The Celery worker decodes photos or representative animation/video frames and creates a safe thumbnail.
5. Local OCR, quality analysis, smart labeling, face analysis, hashes, and OpenCLIP embeddings are generated.
6. PostgreSQL/pgvector retrieves candidates and stores explainable similarity relationships.
7. The UI refreshes gallery, duplicate review, search, smart albums, and status information.
8. User feedback updates persistent people decisions; deletion occurs only after explicit confirmation.

## Expected and achieved outcomes

- A working private media vault with local authentication and strict account isolation.
- Batch-aware exact, near-duplicate, and semantic media matching with understandable evidence.
- Natural-language retrieval plus local multilingual OCR and document-layout data.
- More honest photo-quality scoring and automatic best-shot selection.
- Persistent, private, user-correctable people albums.
- Support for standard/animated images, HEIC/HEIF, common RAW formats, and videos.
- Asynchronous processing with optional CUDA acceleration and automatic CPU fallback.
- A reproducible multi-container platform with Kubernetes and Terraform alternatives.
- CI validation, health checks, Prometheus metrics, Grafana dashboards, and structured logs.
- A zero-additional-software-cost academic deployment based on free/open-source components.
- Current verification: 32 backend tests, frontend unit tests, strict lint/type checks, production builds, Compose validation, migration validation, generated GIF/HEIC/video/OCR runtime smoke tests, and direct Playwright MCP desktop/mobile workflow QA covering authentication, navigation, search, upload validation, batch duplicates, albums, guarded deletion, status, and settings.

## Privacy, security, and limitations

Images, OCR text, embeddings, and face feedback remain inside the self-hosted deployment. Passwords are stored as Argon2 hashes; objects use private UUID keys and time-limited signed links; all image, album, similarity, and deletion queries enforce ownership. Metrics and logs exclude image content, tokens, passwords, and embeddings.

AI similarity, OCR, quality scores, labels, and face clustering can still make mistakes and should be treated as decision support. RAW compatibility depends on LibRaw support for the camera format, and video indexing uses representative frames rather than complete scene-by-scene transcription. The default local deployment uses HTTP and single-instance data services, so TLS, automated backups, secret rotation, malware scanning, and high availability would be required before public or production use.

## Tentative 12-week timeline

| Week | Work |
|---|---|
| 1–2 | Requirements, problem study, scope, privacy, and cost constraints |
| 3–4 | Architecture, repository, database/object model, and Compose foundation |
| 4–5 | Authentication, APIs, PostgreSQL/pgvector, MinIO, and queue integration |
| 5–7 | UI/UX, duplicate intelligence, natural-language search, OCR, labels, and quality scoring |
| 7–8 | Face clustering, feedback controls, smart albums, rich media, and GPU fallback |
| 8–9 | Security review, error handling, automated tests, and performance checks |
| 9–10 | Minikube, Kubernetes, Terraform, CI/CD, Prometheus, and Grafana |
| 10–11 | Release hardening, browser QA, measurements, screenshots, and demo rehearsal |
| 11–12 | Final report, presentation, deployment evidence, and viva preparation |

Activities overlap deliberately so infrastructure, security, documentation, and tests evolve alongside application functionality.

## Future scope

- Undoable encrypted trash and scheduled retention policies.
- Video scene segmentation and local speech transcription.
- Larger offline OCR language packs and handwriting recognition.
- Private geospatial/map albums from optional GPS metadata.
- Encrypted backup/export and disaster-recovery automation.
- A mobile client, multi-node workers, and production-grade GPU scheduling.
