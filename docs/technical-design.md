# ImageVault AI technical design

Updated 7 October 2026 · application 1.2.1 · source baseline `9ee8c0c`.
Authors/supervisor: `[To be supplied]`. Live Azure verification: pending.

## Scope and deployment

The main deliverable is an HTTPS website on an Azure Ubuntu VM, backed by private Azure Blob Storage. Docker Compose runs Caddy/React, FastAPI, Celery, PostgreSQL/pgvector and Redis. Bicep defines the cloud resources; Terraform and Kubernetes examples target the optional local cluster.

In scope: invited accounts, private media upload/review, asynchronous analysis, exact/near/semantic evidence, analytics, advanced OCR/people/albums, failure recovery, CI releases and cost controls. High availability, public identity discovery, automatic deletion, MFA/email recovery and guaranteed accuracy are out of scope.

## Components and configuration

| Component | Design |
|---|---|
| Caddy | Serves compiled React, automatic HTTPS, API forwarding; public ports 80/443 |
| FastAPI | Auth/ownership, quotas, Redis-backed limits, validation, metadata, signed previews, cleanup loop |
| Celery | Single CPU worker for fingerprints, verification and optional model enrichment |
| PostgreSQL 16/pgvector | Accounts, images, jobs, matches, albums/feedback, vectors and durable deletion records |
| Redis | Task broker, heartbeat/model state and atomic shared request limits; Azure uses AOF/noeviction |
| Azure Blob | Private originals/WebP thumbnails, Entra credentials and read-only user-delegation SAS |
| Bicep/cloud-init | VM/network/storage/role/shutdown; release download, checksum verification and container bootstrap |

The VM generator writes a separate private cloud `.env` with independent PostgreSQL/JWT/invitation secrets. Cloud Compose supplies `STORAGE_BACKEND=azure`, the storage endpoint, HTTPS origin, CPU settings, proxy trust range and quotas. `DefaultAzureCredential` obtains VM managed-identity tokens through the metadata endpoint. Account-scoped Storage Blob Data Contributor covers both object operations and user-delegation keys. The local environment uses MinIO and separate secrets.

Cloud defaults: Standard_B2ms x64, 8 GiB RAM, 64 GiB Standard SSD, one 4 GiB-limited worker, 2 GiB originals per user, 15 MiB photos, 100 MiB videos/RAW, 10 files per batch. These constrain application use; they do not cap Azure charges.

## Upload and processing sequence

```mermaid
sequenceDiagram
    participant U as Browser
    participant A as FastAPI
    participant S as Private Blob
    participant D as PostgreSQL
    participant R as Redis
    participant W as Celery
    U->>A: Authenticated multipart batch
    A->>A: Validate limits/content and SHA-256
    A->>S: Store original
    A->>D: Commit image and job
    A->>R: Publish analysis task
    A-->>U: Accepted records and processing state
    R->>W: Dispatch task
    W->>S: Read original and write thumbnail
    W->>W: Fingerprints; optional CLIP/OCR/faces
    W->>D: Persist analysis and verified pair evidence
    U->>A: Gallery/review request
    A->>S: Sign read-only expiring SAS
    A-->>U: Owned records, evidence and previews
```

SHA-256 identifies byte equality within one account; each uploaded copy retains its own object until confirmed deletion. Successful analysis may be reused for exact copies, with a separately stored thumbnail.

Candidate retrieval combines normalized 512-dimensional OpenCLIP/pgvector cosine neighbors with perceptual hash candidates. Verified still-image near duplicates require multiple hash agreement, compatible color/frame evidence and aligned pixels at 32 and 96 scales. Low-detail inputs, missing verification, animations and video do not qualify from a single thumbnail. Strong semantic matches remain manual suggestions. Families require direct pair evidence between all members; transitive chains are insufficient.

Pillow/pillow-heif, rawpy and FFmpeg support available image/RAW/video codecs. Optional Tesseract OCR, labels, quality and YuNet/SFace analysis run inside the deployment. Missing enrichment/model dependencies produce visible warnings while preserving successful fingerprints. Cloud inference uses CPU; optional local GPU configuration supports CPU fallback.

## Data model

| Entity | Principal content |
|---|---|
| users | UUID, normalized email, display name, Argon2 hash, active state |
| images | Owner/batch IDs, object/thumbnail keys, size/type, SHA, hashes, embedding, metadata, state/version/warnings |
| processing_jobs | Image association, pending/running/done/failed state, attempts and bounded diagnostic |
| duplicate_matches | Owned pair, classification, similarity and perceptual/color/frame/pixel evidence |
| people/faces/feedback | Owned persistent person decisions, face vectors and same/different constraints |
| activity_logs | Account-scoped operations and dashboard evidence |
| object_deletions | Object key, attempts/error and creation time; durable cleanup queue |

Alembic migrations `0001`–`0006` establish the schema. Migration `0006` adds deferred object deletion. Do not start old binaries against a newer schema without a reviewed rollback/backup plan. User/time, hash and vector indexes support queries. PostgreSQL stores metadata and vectors, not original image bytes.

## API and authorization

Auth exposes configuration, invitation registration, login and current-user endpoints. Image endpoints cover multipart upload, owned gallery/details, smart search, reindex and confirmed single/bulk deletion. Duplicate, album, dashboard and system endpoints remain owner-scoped. The running API's OpenAPI document is the contract.

Every private query checks authenticated ownership; UUID knowledge alone grants no access. SAS tokens are read-only, HTTPS-only and short-lived (default 30 minutes). Invite codes are checked with constant-time comparison. Cloud rate limits use atomic Redis operations and a configured proxy trust range; Redis failure returns 503 on protected requests.

## Failure handling

| Failure | Result and recovery |
|---|---|
| Invalid/oversized upload or quota | Readable rejection; no valid media record accepted |
| Storage/database upload failure | Rollback/compensation; unresolved object cleanup is recorded where possible |
| Queue publication failure | Original retained, analysis marked retryable; smart-index action after Redis recovery |
| CLIP/OCR/face failure | Preserve fingerprint result and warn; retry enrichment with smart index |
| Storage failure during confirmed deletion | Metadata removal and cleanup record commit together; API retries every 30 seconds and after restart |
| Worker finishes after photo deletion | Any recreated thumbnail is scheduled for cleanup |
| Unavailable database/storage | Readiness unhealthy; backend startup/gateway availability can be affected |
| Missing worker heartbeat | System status degraded; readiness and liveness are separate checks |
| Blob soft-delete retention | Visible vault space can fall before billed bytes disappear |

Readiness requires database and object storage; the system page also reports worker/queue state. Liveness checks the process itself. Deletion cleanup uses row locking/skip-locked records and idempotent storage deletes. Queue publication still requires explicit smart-index retry after recovery; this is not a fully automatic durable task outbox.

## Security and operations

Bicep disables public blobs/shared account keys, enables TLS-only storage, restricts SSH to the deployer's IPv4 CIDR and exposes only web ports publicly. Database/Redis ports are internal. Managed identity removes storage keys, not the need to protect PostgreSQL/JWT secrets. Logs are bounded in cloud Compose; SAS links and invitation codes must stay private.

The deployment is single-VM, lacks MFA/email recovery and needs owner-managed backups. Seven-day Blob/container soft delete does not protect PostgreSQL. Persistent Docker volumes live on the managed OS disk; losing it loses database, Redis, model cache and certificates. Back up the database and media independently and rehearse restore.

Cloud observability uses authenticated System status, health endpoints and container logs. Prometheus/Grafana remain local extensions and are not installed by cloud Compose. Metrics endpoints and Caddy routing are defined in code; do not assume public monitoring consoles exist.

## Delivery and validation

GitHub Actions runs backend/frontend/browser/infrastructure checks before publishing releases. Bundles contain compiled web assets, server/deployment source, synthetic samples, checksum files and source metadata; they do not contain runtime secrets. Initial cloud-init installs a pinned release. Reapplying Bicep does not automatically upgrade application files.

Browser fixtures use SQLite/in-memory objects/deterministic models. PostgreSQL tests need a disposable pgvector database. Azure SDK tests use fakes. Live identity, HTTPS, regional quota, original previews, persistence and restore require a real deployment. See [testing](testing.md), [validation](validation-report.md) and [Windows setup](setup-windows.md).

## Design tradeoffs

- Azure Blob replaces local MinIO in the main deployment; a storage protocol preserves the local option.
- Caddy provides HTTPS and static serving with a small cloud footprint.
- PostgreSQL/pgvector reduces service count compared with a separate vector database.
- Redis/Celery fits a small background-processing workload.
- Conservative pair verification favors fewer false cleanup suggestions over detecting every edit.
- Bicep provisions Azure resources while local Terraform remains scoped to Kubernetes.