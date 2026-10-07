# ImageVault AI project synopsis

Updated 7 October 2026 · application 1.2.1 · source baseline `9ee8c0c`.

## Project title

**ImageVault AI — Azure-Hosted Private Media Storage, Duplicate Detection, Search and Organization Platform**

## Student and supervisor details

- Student name(s), registration number(s): `[To be supplied]`
- Programme, batch, semester, team number: `[To be supplied]`
- Supervisor and department: `[To be supplied]`

## Abstract

ImageVault AI is a browser-based private media vault that stores original files and generated thumbnails in private Azure Blob Storage and keeps account-scoped metadata and vectors in PostgreSQL/pgvector. It addresses repeated backups, edited exports, visually similar photographs and media collections that are difficult to search manually. The user uploads media, compares explainable evidence and explicitly confirms cleanup; the system never deletes files automatically.

SHA-256 identifies byte-identical files before expensive analysis. A Celery worker computes perceptual hashes, color and frame evidence, thumbnails and normalized OpenCLIP embeddings. Still-image near-duplicate decisions additionally require aligned-pixel verification at two scales. Semantic similarity remains a manual review suggestion. Displayed families require direct evidence between every pair, preventing unrelated endpoints from being joined through a chain. Optional OCR, face analysis and AI failures are recorded without discarding successful fingerprint analysis.

The primary deployment uses Azure for Students: an Ubuntu x64 VM runs five Docker containers for Caddy, FastAPI, Celery, PostgreSQL/pgvector and Redis. Caddy serves the React website over HTTPS. Bicep provisions the VM, networking, private Blob container, managed identity, role assignment and scheduled shutdown. The VM identity accesses storage without account keys, and browsers receive expiring read-only user-delegation SAS previews. Invitation-based registration, ownership checks, upload quotas and Redis-backed rate limits restrict access and usage.

GitHub Actions validates application and infrastructure changes and publishes downloadable website/server releases after passing checks. Local Compose with MinIO/Nginx and optional Kubernetes, Terraform, Prometheus and Grafana examples remain available for development or course requirements. Azure resources consume student credit; the system is not unlimited free hosting. Azure connection, live deployment and operating measurements on the student's subscription remain pending.

## Problem statement

Filename comparison cannot reliably find identical media with different names or resized/recompressed copies with different bytes. Semantic matches can also confuse distinct photographs of the same subject. Collections need a private store, understandable matching evidence, responsive background processing and user control over deletion.

A student cloud project must also demonstrate reproducible infrastructure, identity and access management, secure web access, CI and operational cost control. ImageVault combines these concerns in a small deployment that can be shown through a browser without running the full platform on the presentation laptop.

## Objectives

1. Store originals and thumbnails privately in Azure Blob Storage with account-isolated database records.
2. Identify exact copies and conservatively verify near duplicates, keeping semantic suggestions separate.
3. Process uploads asynchronously and expose progress, warnings and retry controls.
4. Provide gallery search, duplicate review and storage analytics as four primary classroom pages.
5. Retain advanced semantic search, OCR, quality scoring, events, bursts and user-correctable people albums.
6. Provision cloud infrastructure with Bicep and run the app with Docker Compose.
7. Apply HTTPS, managed identity, expiring previews, invitation signup, quotas and rate limits.
8. Demonstrate CI, reproducible releases, failure recovery, backups and credit-conscious operations.

## Modules

| Module | Responsibility |
|---|---|
| Authentication | Argon2 password hashes, expiring JWTs, invitation-based signup and ownership checks |
| Upload/storage | Content/size validation, SHA-256, batch IDs, private UUID-keyed originals and thumbnails |
| Duplicate intelligence | Exact references, multi-hash/color/frame evidence, two-scale pixel verification and pair-complete families |
| Semantic retrieval | OpenCLIP vectors and pgvector cosine candidates; advisory content matches |
| Advanced organization | OCR, document layout, quality, labels, events, burst selection, local-to-VM face inference and private feedback |
| User interface | Upload, Gallery, Duplicate review, Dashboard; Advanced contains albums, status and settings |
| Reliability | Retryable analysis, transactional deletion records, automatic deferred object cleanup and visible warnings |
| Cloud/DevOps | Azure VM/Blob, managed identity, Caddy HTTPS, Bicep, Compose, GitHub Actions and release checksums |

“Local inference” means inside the self-hosted VM or local deployment, not necessarily on the user's laptop. Azure hosts media and compute; the app does not use Azure OpenAI, Azure AI Vision or a public face-identification API.

## Tools and technologies

| Concern | Technology |
|---|---|
| Cloud infrastructure | Azure for Students, Ubuntu VM, Blob Storage, virtual network, NSG, managed identity |
| Main IaC/deployment | Bicep, cloud-init, Docker Compose |
| Web/gateway | React, TypeScript, Vite, Tailwind CSS, Caddy HTTPS |
| API/auth | FastAPI, Pydantic, SQLAlchemy, Argon2, JWT |
| Data/jobs | PostgreSQL 16, pgvector, Alembic, Redis, Celery |
| Media/AI | OpenCLIP/PyTorch, Pillow, ImageHash, OpenCV YuNet/SFace, Tesseract, FFmpeg, rawpy |
| Version control/delivery | Git, GitHub Actions, checksum-verified ZIP/TAR.GZ releases |
| Optional local extensions | MinIO, Nginx, Minikube/Kubernetes, Terraform, Prometheus/Grafana |

## Workflow

1. An invited user registers or signs in over HTTPS.
2. The API checks ownership, request limits, file signatures, batch and original-file quotas.
3. It stores the original in Blob Storage, calculates SHA-256 and commits database/job state.
4. Exact copies are recognized independently of AI; Redis dispatches remaining analysis.
5. The worker creates thumbnails/fingerprints, attempts optional model enrichment and records warnings.
6. pgvector/hash retrieval supplies candidates; pixel verification and conservative gates classify evidence.
7. The browser shows private previews, review groups, analytics and advanced albums.
8. Confirmed deletion commits metadata changes and durable cleanup records together; failed object cleanup retries.

## Cloud design and cost

The default VM is Standard_B2ms, 2 vCPU/8 GiB RAM, with a 64 GiB Standard SSD. PostgreSQL, Redis and model caches persist in VM Docker volumes; original media persists in Blob Storage. Database and queue ports are private. Seven-day Blob soft delete helps with accidental removal but does not back up the database.

Microsoft's current student offer includes USD $100 credit for 12 months and selected allowances without a card at signup. This VM consumes credit, and availability depends on region/quota. Daily shutdown defaults to 20:00 UTC (01:30 IST the next day); the VM must be started for a demonstration. Deallocation stops compute billing, while disk, public IP and Blob usage can remain billable. Budgets notify rather than cap expenditure. See [cost analysis](cost-analysis.md) and Microsoft's linked offer terms.

## Implementation and validation status

Application and deployment definitions are present in GitHub main. This folder was updated from `bc7cea7` to `9ee8c0c`; academic docs were revised to match the Azure architecture. The user's Azure subscription has not yet been connected or provisioned through this update.

Automated coverage includes authentication, upload isolation, exact copies, pixel evidence, conservative families, degraded models, deletion/queue failures, frontend behavior and desktop/mobile browser fixtures. Real PostgreSQL checks require a disposable database; storage/browser fakes do not establish live Azure behavior or real-world AI accuracy. Actual checks from this update are recorded in [validation-report.md](validation-report.md); no unmeasured accuracy, latency or savings is claimed.

## Security and limitations

Azure blobs remain private; storage-account shared keys are disabled in the template. User-delegation SAS URLs remain sensitive until expiry. Passwords, application secrets and invitation codes are kept outside version control. Images and embeddings reside in the self-hosted Azure deployment, rather than a hosted inference API.

One VM and single data-service instances limit availability. Owners must arrange independent database/media backups. Accounts have no email recovery or MFA. OCR, face clustering and semantic/near-duplicate decisions can be wrong. Heavy crops/edits and changed document text require careful full-resolution review; sampled video frames cannot prove whole-video equivalence. Live managed identity, regional quota, HTTPS and persistence must be verified after deployment.

## Tentative 12-week timeline

| Weeks | Work |
|---|---|
| 1–2 | Requirements, media privacy, student eligibility and credit constraints |
| 3–4 | API/data model, storage abstraction, containers and initial UI |
| 4–6 | Authentication, uploads, exact/visual evidence, review and analytics |
| 6–8 | Advanced intelligence, failure recovery, fixtures and browser checks |
| 8–10 | Azure Bicep/identity/HTTPS, CI releases, cost controls and backup rehearsal |
| 10–11 | Live deployment validation, screenshots and independent measurements |
| 11–12 | Final report, presentation, contribution evidence and viva preparation |

## Future scope

Automated encrypted backups and restore rehearsal, undoable trash, independent labeled evaluation, larger-library candidate indexing, multi-worker capacity planning, video scene/transcription analysis, mobile clients and improved account recovery.

## References and next steps

[Windows setup](setup-windows.md) · [Architecture](architecture.md) ·
[Technical design](technical-design.md) · [Validation report](validation-report.md) ·
[Presentation outline](presentation-outline.md). Complete student/supervisor fields
and replace evidence placeholders only after an actual deployment.