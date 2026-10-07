# Test coverage and reliability

Updated 7 October 2026. This describes the available checks, not a claim that
every check ran on this Windows PC. Actual results are in
[validation-report.md](validation-report.md).

ImageVault 1.2.1 adds regression tests for upload, queue, storage, authentication,
page navigation, duplicate-family integrity, and desktop/mobile browser flows.
Passing GitHub checks are required before the automatic download release job runs.

## Run the checks

```bash
python -m venv .venv
.venv/bin/pip install -e 'backend[dev]'
cd backend
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q
cd ../frontend
npm ci
npm run lint
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
npm audit --audit-level=high
```

On Windows, use the equivalent virtual-environment Python paths. If Python is
already on PATH, set `IMAGEVAULT_TEST_PYTHON=python` for the browser tests. This
runs a website test server; it does not build a desktop application.

For an explicit PowerShell setup from the repository root with Python 3.12 and
Node installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e 'backend[dev]'
Set-Location backend
$env:DEBUG = 'false'
..\.venv\Scripts\ruff.exe check app tests
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm.cmd ci
npm.cmd run lint
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
$env:IMAGEVAULT_TEST_PYTHON = '"' + (Resolve-Path ..\.venv\Scripts\python.exe).Path + '"'
npm.cmd run test:e2e
npm.cmd audit --audit-level=high
```

Do not use Azure CLI's private Python runtime for this environment. Backend
dependencies support Python 3.11–3.13; CI uses 3.12. Node 22 is the CI baseline.
The quoted Python path is required when the folder name contains spaces.
The explicit `DEBUG=false` avoids inheriting a non-boolean host variable.

The browser tests start and stop their own disposable API and production website
preview. They cover signup with an invitation, uploading an original and an exact
copy, reviewing the pair, cancelling and confirming deletion, preserving the
keeper, signing out, and access protection. Desktop and mobile viewports both run
this flow. Tests also check readable login errors, browser runtime errors and
horizontal overflow. Failure screenshots and traces are retained in GitHub Actions.

Additional desktop/mobile flows cover invalid invitation codes, unsupported and
corrupt files, over-limit batches, an interrupted upload followed by retry,
refresh persistence, and a second account denied access to another account's
photo. There are ten browser scenarios in total across the two viewport projects.

Deployment-script tests verify independent secrets, refusal to overwrite an
existing environment, rejection of invalid endpoints, safe archive contents,
release checksums and exclusion/refusal of private runtime files.

The browser API uses SQLite, in-memory object storage, and deterministic model
outputs. It exercises real HTTP, authentication, image validation, processing and
pixel verification. These fixtures do **not** verify an Azure deployment or the
accuracy of OpenCLIP, OCR or face models on real-world photographs.

## PostgreSQL and migrations

GitHub Actions supplies PostgreSQL 16 with pgvector and sets `TEST_POSTGRES_URL`
to a disposable database named `imagevault_test`. Tests exercise real vector
retrieval, resized-copy verification, and migration upgrade/rollback/re-upgrade.
The PostgreSQL tests skip locally if that variable is absent. Never point them at
a production database: the tests create and drop tables.

## Detection corpus

A reproducible synthetic corpus checks 30 resized, recompressed and mildly
brightened copies, and 10 unrelated image pairs with deliberately high semantic
scores. Confirmed copies require aligned pixel evidence; unrelated pairs must
never become confirmed perceptual duplicates. Existing tests cover hash
collisions, mirrors, unavailable models, corrupted media and exact-analysis reuse.
This corpus is regression coverage, **not** a universal accuracy percentage.
For a class presentation, demonstrate the supplied samples and inspect every
visual suggestion before deleting. SHA-256 exact matches mean identical bytes;
visual resemblance alone does not establish an exact duplicate.

## Failure recovery

* Failed queue publication keeps the original, marks analysis retryable, and
  reports the failure. Use **Rebuild smart index** after the queue is restored.
* Deletion first commits metadata removal and an object-cleanup record in one
  transaction. Storage outages retain that record; the API retries cleanup every
  30 seconds, including after restart. Blob deletion is idempotent.
* Migration `0006` adds `object_deletions`. Upgrade the database before starting
  the updated API and worker. The provided deployment already runs migrations.
* A worker finishing after a user deletes a photo schedules cleanup for any
  thumbnail it recreated. Old/failed visual evidence is hidden until re-analysis.
* Cloud storage soft-delete/versioning policies may retain deleted bytes for their
  configured retention period. Vault space and billed physical storage can differ.

To verify a real deployment, check **System status**, upload the classroom samples,
wait for the worker to finish, test duplicate review, refresh the website, and
verify deletion in the Blob account after its retention policy allows removal.
