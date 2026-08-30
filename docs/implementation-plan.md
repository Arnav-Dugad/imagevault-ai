# ImageVault AI implementation plan

## Objective

Build a production-style, self-hosted private-cloud image platform that runs at no additional software or cloud-service cost. The demonstrable academic focus is Cloud Computing and DevOps; local AI similarity is the workload deployed on that platform.

## Architectural decisions

- **Web client:** React, TypeScript, Vite, Tailwind CSS, Framer Motion, Recharts, and Lucide.
- **API:** FastAPI with versioned REST routes, OpenAPI, request IDs, structured logs, Prometheus metrics, JWT authentication, and explicit user-scoped authorization.
- **Data:** PostgreSQL with pgvector stores relational metadata and 512-dimensional normalized image embeddings. Alembic manages schema migrations.
- **Objects:** MinIO stores UUID-keyed originals and WebP thumbnails. PostgreSQL never stores image binaries.
- **Async processing:** Redis and Celery decouple upload from CPU/GPU image processing. The upload API performs the inexpensive SHA-256 check before queueing non-exact images.
- **Image intelligence:** Pillow extracts safe metadata and pHash values. OpenCLIP ViT-B/32 generates local embeddings on CPU by default and uses CUDA automatically when available.
- **Delivery:** Docker Compose is the primary laptop demonstration path. Minikube manifests and Terraform provide orchestration and IaC demonstrations without any public-cloud account.
- **Observability:** Prometheus scrapes API and worker metrics; Grafana is provisioned with an ImageVault dashboard; health endpoints distinguish liveness from readiness.

## Delivery phases

### Phase 1 — Foundation

- Create the monorepo layout, configuration contract, Docker Compose topology, database and object-store services.
- Implement backend settings, logging, database lifecycle, MinIO initialization, and health endpoints.
- Build the responsive application shell and reverse-proxy routing.

### Phase 2 — Core image management

- Implement registration, login, current-user, JWT expiry, and Argon2 password hashing.
- Implement validated batch upload, UUID object keys, metadata persistence, gallery filters/sorting/pagination, previews, details, and safe deletion.
- Enforce ownership checks for every user resource.

### Phase 3 — duplicate and similarity processing

- Detect exact duplicates with SHA-256 before expensive processing.
- Generate thumbnails, pHash, OpenCLIP embeddings, and pgvector nearest-neighbour matches asynchronously.
- Persist duplicate relationships and expose similarity and duplicate-review APIs.

### Phase 4 — product interface

- Deliver login/register, dashboard, upload, gallery, image detail, duplicate review, monitoring, system status, and settings screens.
- Include progress, loading, error, empty, and confirmation states with responsive and keyboard-accessible behavior.

### Phase 5 — Cloud and DevOps

- Harden component images and Compose health checks.
- Add Minikube-ready Kubernetes Deployments, Services, ConfigMaps, Secrets, PVCs, probes, limits, and an optional HPA.
- Add Terraform configuration, GitHub Actions validation, Prometheus configuration, and provisioned Grafana dashboards.

### Phase 6 — quality and demonstration

- Add API and processing tests, frontend tests, demo-image generation, traffic generation, benchmark, and guarded reset utilities.
- Validate every tool available in this environment; record tooling that requires manual Windows validation.

### Phase 7 — academic deliverables

- Complete the README, architecture and technical design, synopsis draft, demonstration script, contribution template, presentation outline, viva guide, cost analysis, and Mermaid diagrams.
- Leave student, supervisor, screenshot, and measured-performance fields explicitly marked for later completion.

## Verification gates

1. Python modules compile and backend tests pass where the Python runtime is available.
2. Frontend lint, unit tests, and production build pass.
3. Docker Compose configuration resolves without interpolation errors where Docker is available.
4. Kubernetes YAML parses and client-side validation runs where `kubectl` is available.
5. Terraform formatting and validation run where Terraform is available.
6. No committed secret, uploaded image, model weight, generated data volume, build output, or dependency directory is present.

## Definition of done

The repository tells one consistent story: a private S3-compatible image workload with per-user isolation and local duplicate intelligence, containerized with Docker, orchestrated by Kubernetes, declared with Terraform, checked by GitHub Actions, and observed with Prometheus and Grafana. AI-based matches are advisory and deletion is always explicit.
