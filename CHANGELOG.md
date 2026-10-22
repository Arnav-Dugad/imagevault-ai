# Changelog

## 3.1.0 (2026-10-22)

**Free AI recognition**, running inside the app: no paid AI service, nothing sent to third parties.

- **People:** faces are found (YuNet) and recognised (SFace), so the same person is grouped across photos, even in group photos. People can be named, and photo outlines show who is where.
- **Smart search:** find photos by describing them ("a cat", "a palace at sunset"). Searches for something that isn't in any photo return nothing instead of guesses.
- **Same subject, different shot:** CLIP suggests different photos of the same scene. They're shown separately from copies and never deleted automatically.
- AI analysis runs in the background with live progress on the Home page, and appears as a fifth service on the Cloud page.
- Models are downloaded once from pinned versions and verified by SHA-256 (about 190 MB); they use about 320 MB of memory, so they fit the free App Service plan.
- The demo zip now has 32 photos, including Taj Mahal shots, cats and public-domain portraits for the People page.
- Three new tests use real public-domain photos; the CI pipeline caches the models.

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
