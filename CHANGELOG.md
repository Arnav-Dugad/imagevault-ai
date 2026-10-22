# Changelog

## 3.0.0 (2026-10-22)

ImageVault is now a cloud website on Microsoft Azure, built to the CCD mini-project guidelines.

- **Website on Azure App Service**, replacing the desktop app.
- **Azure Database for PostgreSQL** stores photo data (SQLite is still used when running locally).
- **Azure Blob Storage** holds photos and thumbnails, accessed with a managed identity, so no keys are needed.
- **Application Insights** monitors requests, errors and logs.
- **Terraform** (`infra/`) creates every Azure resource, including a **budget with email alerts**.
- **GitHub Actions CI/CD:** tests run in local and cloud mode (PostgreSQL + Azure Storage emulator). Pushes to `main` deploy to Azure with passwordless OIDC sign-in, followed by a smoke test.
- **New Cloud page** with live health and response time of each Azure service, an architecture diagram and the deployed commit.
- **Real demo photos** (from Unsplash) with exact, resized, compressed and edited copies plus look-alikes, downloadable from the website.
- Clearer duplicate review: the best copy is chosen by resolution and quality, and every other photo is labelled by how it relates to it.
- New docs: Azure deployment guide, technical design document, demo guide.
- Removed: the Windows desktop app, PyInstaller packaging and the in-app Azure connection form.

## 2.0.0 (2026-10-22)

Simple Windows desktop app (FastAPI + SQLite + React) with optional Azure Blob Storage, replacing the multi-container 1.x stack.

## 1.x

Multi-container edition (PostgreSQL, Redis, Celery, MinIO, CLIP, Kubernetes, Terraform). Available in the git history and older releases.
