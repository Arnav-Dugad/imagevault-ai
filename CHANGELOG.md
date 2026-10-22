# Changelog

## 2.0.0 (2026-10-22)

A complete rewrite that makes ImageVault much simpler to run and use.

- **New desktop app for Windows:** download one `.exe` and double-click it. Nothing to install, no Docker, no database server.
- **Azure Blob Storage in a few clicks:** paste your storage account's connection string in Settings. Photos already on your computer keep working.
- **Optional website on Azure App Service** (free F1 plan) with password protection, using `packaging/deploy-azure.ps1`.
- **Duplicate detection:** exact copies (SHA-256) and similar photos (perceptual hashes). Identical files are stored only once.
- **Redesigned app:** Home, Photos, Upload, Duplicates and Settings pages, with a photo viewer, side-by-side duplicate review and one-click removal of exact copies.
- **Simpler setup:** one Python process with SQLite replaces PostgreSQL, Redis, Celery, MinIO, Prometheus, Grafana, Kubernetes and Terraform. The AI models (CLIP, face recognition, OCR) were removed to keep the app small and fast.
- New beginner-friendly docs: [Azure guide](docs/azure.md) and [how it works](docs/how-it-works.md).

Version 1.x (the multi-container Azure VM edition) is still available from the [older releases](https://github.com/Arnav-Dugad/imagevault-ai/releases) and the git history.
