# Changelog

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
