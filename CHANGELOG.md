# Changelog

## Azure setup and reliability update — 7 October 2026

- Synchronize this folder with GitHub main `9ee8c0c` (application 1.2.1).
- Add a Windows PowerShell Azure connection/deployment walkthrough and optional local startup.
- Align synopsis, technical design, implementation plan, presentation, viva and contribution docs with Azure VM/Blob, Bicep/Compose, managed identity and student-credit limits.
- Replace stale validation claims with evidence from this update and pending live Azure checks.
- Align environment/Compose version labels with 1.2.1 while preserving local secrets.
- Make keeper selection deterministic when quality and timestamps tie, preserving exact-copy selection in mixed review families.
- Add desktop/mobile validation, upload interruption/retry, persistence and cross-account authorization checks.
- Test cloud secret generation, environment preservation and secret-safe release packaging.
- Document simple priorities for the next version: Trash, backups, clear retry controls and fewer optional features.

## 1.2.1

- Add transaction-backed deferred object cleanup, including storage outages and worker/deletion races.
- Strengthen queue failure, account isolation and duplicate-evidence regression coverage.
- Add frontend/API recovery checks and desktop/mobile Playwright workflows.
- Gate release publication on browser checks alongside application and infrastructure checks.

## 1.2.0

- Simplify Azure hosting to five containers with Caddy serving the website directly; preserve shared request limits.
- Keep four primary pages and move advanced tools into expandable navigation.
- Require multi-hash consensus and spatial pixel verification for still-image near duplicates; label semantic matches for review.
- Stop transitive match chains from producing unsupported duplicate families; select only exact copies in bulk.
- Keep fingerprint processing available when AI or enrichment fails, expose warnings, and support retries.
- Rank fingerprint candidates before limiting; handle pgvector arrays and invalid vectors correctly.
- Add reliability regressions, a six-image downloadable demonstration, and a focused classroom presentation guide.


## 1.1.0

- Azure Blob Storage provider using VM managed identity and HTTPS-only read-only
  user-delegation signed URLs, with delegation-key caching.
- Azure Bicep deployment: 8 GiB Ubuntu VM, private blobs, restricted SSH,
  daily auto-shutdown, HTTPS gateway, and private database/queue ports.
- Small cloud Compose stack with CPU worker limits and bounded container logs;
  MinIO and monitoring containers remain available in the local academic setup.
- Invitation-based cloud signup, optional closed registration, per-account
  original-file quotas, and authentication request limits.
- Accurate deployment/worker status, configurable monitoring links, reduced-motion
  support on status cards, and an in-app GitHub download link.
- Redis no longer evicts queued AI jobs. Network storage writes and health checks
  run outside the asynchronous API event loop.
- Every successful main-branch CI run publishes complete ZIP/TAR.GZ installation
  website/server bundles with compiled UI, checksums, and source commit metadata.
- Streaming, verified MinIO-to-Blob migration and Azure operations/backup guide.
- Updated vulnerable frontend tooling and removed the redundant Autoprefixer dependency.

Azure hosting uses student credit; live quota, deployment, and RBAC must be verified
in your own subscription. Existing local data is not transferred automatically.
