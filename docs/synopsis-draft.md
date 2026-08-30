# Project synopsis draft

## Project title

**ImageVault AI — Intelligent Private Cloud Image Storage, Duplicate Detection & Visual Similarity Platform**

## Student details

- Student name(s): `[To be supplied]`
- Registration number(s): `[To be supplied]`
- Programme / batch / semester: `[To be supplied]`
- Team number: `[To be supplied]`

## Supervisor details

- Supervisor name: `[To be supplied]`
- Department: `[To be supplied]`

## Synopsis / abstract

ImageVault AI is a self-hosted private-cloud image-management platform designed to reduce duplicate storage and improve organization of personal media. Users upload images to S3-compatible MinIO object storage while PostgreSQL stores user-scoped metadata, processing state, cryptographic hashes, and pgvector embeddings. SHA-256 identifies byte-identical files before a background worker performs more expensive thumbnail, perceptual-hash, and OpenCLIP visual-similarity processing locally.

The project emphasizes Cloud Computing and DevOps. The React client, FastAPI service, Redis job queue, AI worker, PostgreSQL/pgvector, MinIO, Nginx, Prometheus, and Grafana services are containerized with Docker. Docker Compose provides the primary laptop deployment, while Kubernetes on Minikube demonstrates orchestration, probes, persistent volumes, configuration, secrets, resource controls, and horizontal scaling. Terraform defines the local Kubernetes infrastructure, GitHub Actions validates changes, and Prometheus/Grafana provide monitoring and visualization. The required system uses only free/open-source software and needs no external AI API or public-cloud subscription.

## Problem statement

People accumulate phone photographs, WhatsApp images, screenshots, downloads, edited versions, and repeated backups. This produces byte-identical copies, resized or recompressed versions, wasted capacity, and a manual cleanup problem. Filename comparison is insufficient: identical bytes can have different names, while visually equivalent images can have different bytes. Many storage products retain these copies without presenting clear exact-versus-near-duplicate evidence.

ImageVault AI addresses the problem with cryptographic hashing and local visual embeddings inside a demonstrable private-cloud architecture. It does not claim perfect AI classification and never deletes content automatically.

## Proposed solution

1. **Authentication module:** self-hosted registration/login and user isolation.
2. **Image storage module:** validated batch intake, UUID object keys, MinIO originals/thumbnails, PostgreSQL metadata.
3. **Exact duplicate module:** per-user SHA-256 lookup with 100% byte-equality evidence.
4. **AI visual similarity module:** pHash, normalized OpenCLIP embeddings, pgvector cosine retrieval.
5. **Duplicate review module:** grouped evidence and explicit deletion confirmation.
6. **Analytics dashboard:** image, storage, savings, format, activity, and queue information.
7. **Cloud infrastructure module:** Docker Compose and Minikube/Kubernetes.
8. **DevOps automation module:** Terraform and GitHub Actions.
9. **Monitoring module:** health probes, structured logging, Prometheus, and Grafana.

## Tools and technologies

| Classification | Technology |
|---|---|
| Private cloud / orchestration | Kubernetes, Minikube |
| Containerization | Docker, Docker Compose |
| Object storage | MinIO |
| Database / vector search | PostgreSQL, pgvector |
| Backend / queue | FastAPI, Celery, Redis |
| Frontend | React, TypeScript, Vite |
| Local AI / image processing | OpenCLIP, PyTorch, Pillow, ImageHash |
| Infrastructure as Code | Terraform |
| CI/CD | GitHub Actions |
| Monitoring / visualization | Prometheus, Grafana OSS |
| Reverse proxy | Nginx |
| Version control | Git, GitHub |

## Expected outcomes

- A working private image vault with local authentication and user isolation.
- Clear separation of byte-identical, perceptual, and embedding-based evidence.
- Asynchronous CPU-compatible image processing with optional CUDA acceleration.
- A reproducible multi-container platform and Minikube deployment.
- Declarative infrastructure, CI validation, health checks, metrics, dashboards, and structured logs.
- A repeatable live demonstration using copyright-safe generated images.
- Actual measurements and screenshots to be collected after final deployment: `[results placeholder]`.

## Tentative 12-week timeline

| Week | Work |
|---|---|
| 1–2 | Requirements, literature/product research, scope and cost constraints |
| 3–4 | Architecture, proof of concept, repository and Compose foundation |
| 4–5 | System/database/API design and cloud architecture review |
| 5–6 | UI/UX, authentication, backend APIs, PostgreSQL and MinIO integration |
| 4–7 | Core implementation, tests, hashes, AI worker, containerization |
| 7–8 | Full integration, error handling, security and performance checks |
| 8–9 | Minikube, Kubernetes, Terraform, CI/CD, Prometheus and Grafana |
| 9–10 | Release candidate, local deployment, debugging and demo rehearsal |
| 11 | Documentation, screenshots, test evidence, measurements and slides |
| 12 | Final demonstration and viva preparation |

Activities overlap deliberately so infrastructure and tests evolve alongside application code.
