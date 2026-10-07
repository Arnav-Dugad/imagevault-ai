# Validation report

Executed 7 October 2026 in the Windows project folder.

## Source and documentation baseline

- GitHub source: `main`, commit `9ee8c0c`, application 1.2.1.
- Folder fast-forwarded from `bc7cea7`; working tree was clean before synchronization.
- Latest stable release checked through GitHub's API: `v1.2.1-build.25`, published
  6 October 2026, with ZIP, TAR.GZ, SHA256SUMS and release metadata.
- Synopsis and academic/operational docs updated for Azure VM/Blob, Bicep/Compose,
  managed identity, HTTPS, conservative duplicate evidence and finite student credit.
- Existing private `.env` retained; only APP_VERSION=1.2.1 and ANALYSIS_VERSION=6
  synchronized. Database/object/JWT/Grafana secrets were not regenerated.
- This update also includes additional browser/deployment-script coverage and
  a deterministic keeper-selection fix found during the deeper regression run.
  GitHub Actions records the checks for the pushed commit in the repository's
  [Actions history](https://github.com/Arnav-Dugad/imagevault-ai/actions).

## Executed checks

| Check | Result and scope |
|---|---|
| Frontend locked dependency install | Passed, 312 packages installed |
| ESLint | Passed, zero warnings required by script |
| Vitest | 4 files passed, **17 tests passed** |
| TypeScript/Vite production build | Passed; compiled frontend in ignored `frontend/dist` |
| npm audit, high-severity gate | Passed; **0 vulnerabilities reported** at execution |
| Backend Ruff | Passed: “All checks passed!” |
| Backend pytest | **136 passed, 2 skipped**; local skips require real PostgreSQL |
| Playwright Chromium | **10 passed** across desktop/mobile projects |
| Azure Bicep build | Passed; compiled ARM JSON in ignored `tmp` |
| Optional Terraform fmt/init/validate | Passed; no plan/apply or infrastructure changes |
| YAML/JSON syntax | Parsed 17 infrastructure/Compose/CI YAML and 3 JSON files |
| Documentation links | Checked README/INSTALL/CHANGELOG and all docs; local links/anchors passed |
| Documented PowerShell | All PowerShell code blocks parsed with Windows PowerShell's AST parser |
| Git whitespace check | Passed |
| Real ZIP/TAR.GZ packaging smoke check | Both archives verified: 217 files, matching members, valid SHA-256 checksums, required source/docs/compiled website present |
| Publish-content review | Staged files and archives scanned against private environment values; credentials, dependencies and runtime data excluded |

The browser flows cover invitation registration, original/exact-copy upload,
processing completion, evidence review, cancelling and confirming deletion,
keeper preservation, logout/protected routing, readable credential errors,
runtime console errors and horizontal overflow. The test fixture uses actual HTTP
and application routes with SQLite, in-memory storage and deterministic embeddings.
It does not use the user's real media or connect to Azure.

The expanded browser checks cover invalid invitation codes, unsupported/corrupt
uploads, batch limits, network interruption/retry, refresh persistence and a
second account unable to read/delete the owner's photo. Deployment-script tests
cover secret generation without disclosure, refusing to replace an existing
environment, invalid configuration, archive contents/checksums and refusing
tracked credentials or path traversal.

The deeper run exposed inconsistent keeper selection when quality and creation
timestamps were tied. UUID/set order could choose a visually related image and
hide an exact-copy candidate. Tied keepers now favor a representative with exact
copies and use a stable UUID tie-break. A regression with both UUID orders and
identical timestamps verifies this behavior. Higher-quality/older keeper ranking
otherwise remains in place. The full backend suite passed after the fix.

## Validation environment and adjustments

Node 24.16.0/npm 11.13.0 were available on the host; CI uses Node 22.
A project-specific Python 3.12.15 test environment was prepared in ignored
`.venv`, with download/cache tooling under ignored `tmp`. This is a development
test environment, not the complete media-inference worker container.

Windows sandbox restrictions prevented initial npm-cache access and Vite path
reads. Retried checks used the project cache and the required execution access;
the successful results above are from those retries. The host supplied
`DEBUG=release`, which is not a valid Pydantic boolean; setting `DEBUG=false`
for the test process resolved startup without changing application code.
Browser startup requires a quoted Python executable path because this folder
name contains spaces. Both adjustments are documented in [testing.md](testing.md).
New tests that create temporary files used a fresh directory under ignored
`tmp` to avoid the sandbox's restricted shared Windows pytest temporary directory.

Bicep validation used Azure CLI 2.90.0/Bicep 0.47.16 with a separate temporary
configuration directory. It did not log into the user's Azure profile or deploy
resources. Terraform 1.15.8 validated the optional local-cluster files; provider
downloads do not establish a working Kubernetes deployment. The generated
Terraform lock file was removed to avoid an unrelated repository edit.

## Not executed or still pending

| Check | Reason / required next step |
|---|---|
| Azure subscription login/activation and regional quota | User must complete their own sign-in and student eligibility |
| Live Azure VM/Blob deployment | No Azure resources were provisioned by this update |
| Managed identity, RBAC and real user-delegation SAS | Verify on the deployed VM; SDK tests use fakes |
| Real HTTPS certificate and browser previews | Wait for cloud-init/Caddy and verify from the deployed URL |
| Docker builds/Compose full-stack health | Docker Desktop absent on this PC; Azure VM will install Docker |
| PostgreSQL/pgvector migration/vector tests on this PC | Two local tests skipped; GitHub CI supplies a disposable real pgvector database and runs both |
| OpenCLIP/OCR/face inference and media codecs | Real worker/model downloads not run; deterministic test doubles are limited evidence |
| Live outage recovery, persistence, backup and restore | Rehearse with disposable data after deployment |
| Kubernetes rollout/scaling/monitoring | Optional local extension, not executed |
| Real-world accuracy, latency and operating cost | No independent corpus, live benchmark or actual Azure spend measured |

Passing tests are evidence for covered cases, not a universal detection guarantee.
See [detection reliability](detection-reliability.md).

## Live Azure acceptance checklist

Follow [Windows setup](setup-windows.md) first, then record dates, screenshots and
actual outputs for:

1. Selected Azure for Students subscription, permitted VM SKU/region and remaining credit.
2. Successful Bicep deployment and cloud-init/container startup.
3. Private `imagevault` Blob container, disabled account keys and VM identity's account-scoped role.
4. HTTPS registration with invitation, login and Azure system status.
5. Original/thumbnail previews; exact-copy and verified near-duplicate demonstration.
6. Two-account authorization isolation and confirmed cleanup; retained soft-deleted billed bytes explained.
7. VM deallocation/start and account/media persistence.
8. Independent PostgreSQL/media backup and verified restore.
9. Actual CI release checks and measured resource usage.

Record the real deployment/release tag if it differs from this report's baseline.
Fill academic screenshot/measurement placeholders only from these checks.
