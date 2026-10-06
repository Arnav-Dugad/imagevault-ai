# ImageVault AI

Private photo storage and duplicate review, built for a simple classroom demonstration.
Use the deployed website in any modern browser.

**[Download website/server bundle](https://github.com/Arnav-Dugad/imagevault-ai/releases/latest)** · **[Azure setup](docs/azure-students.md)** · **[Five-minute presentation](docs/demo-script.md)**

## One primary deployment

Azure for Students hosts an Ubuntu VM and private Azure Blob Storage. Five containers
run Caddy (HTTPS and the React website), FastAPI, a Celery worker, PostgreSQL/pgvector,
and Redis. Managed identity avoids storage account keys. Signed previews expire;
invitation-based signup and upload quotas control access and usage.

The default 8 GiB CPU VM uses student credit. This is not unlimited free hosting.
Keep your spending limit enabled, check regional pricing and quota, and deallocate
compute between demos. Disks, public IP and stored data can still incur charges.
See [cost controls](docs/cost-analysis.md). A live Azure account is not included.

Start with [INSTALL.md](INSTALL.md) and the [Azure deployment guide](docs/azure-students.md).
Bicep provisions the infrastructure; Docker Compose runs the application. No Windows
application is built or needed.

## Four main pages

- **Upload:** validate and upload photos to private storage.
- **Gallery:** browse originals, search, and inspect image details.
- **Duplicate review:** compare evidence and confirm cleanup.
- **Dashboard:** view uploads, storage and potential exact-copy savings.

**Advanced** contains smart albums, system status and settings. People albums, OCR,
quality scores, semantic search and supported video/RAW formats remain available.
The [architecture guide](docs/architecture.md) explains the services and pipeline.

## Reliable detection, with honest limits

| Result | Evidence | Cleanup behavior |
|---|---|---|
| Exact copy | SHA-256 of identical file bytes | Included in “Select exact”; confirmation required |
| Near duplicate | Multiple hashes, compatible colors/frame, and aligned pixels at two scales | Manual comparison |
| Similar content | Strong CLIP content match | Manual review; different shots may resemble one another |

Families require direct evidence between every pair; matching through a chain is
insufficient. Fingerprint processing survives unavailable AI/OCR/face models;
image details explain incomplete analysis and **Upgrade smart index** retries it.
Scores indicate resemblance, not deletion-safety probabilities.

After upgrading an existing library, click **Duplicate review → Upgrade smart index**
and let version-6 processing finish. Older unverified visual families are hidden
until rebuilt. Back up data before upgrading or deleting photos.

No real-world accuracy percentage is claimed. Crops, heavy edits, low-detail images,
changed document text and videos need particular care. Read the
[reliability and evaluation guide](docs/detection-reliability.md).

## Present it in class

Each release includes six original synthetic demo images: an original, exact copy,
resized copy, compressed copy, mirrored review case and unrelated document. Warm
the model and rehearse before class. Follow the [five-minute demo](docs/demo-script.md).
Source checkouts can generate the samples with `python scripts/generate_demo.py`
after installing Pillow.

Kubernetes, Terraform and Prometheus/Grafana remain optional academic extensions.
Use them only when the course rubric requires them. The main Azure website uses
Compose and Bicep; [local development](docs/local-development.md) uses MinIO.

## Tests and downloadable releases

GitHub Actions checks Python lint/tests, frontend audit/lint/tests/build, Compose,
Dockerfiles, Caddy, Bicep, Kubernetes and Terraform. Every passing `main` build
publishes ZIP and TAR.GZ bundles with the compiled website, server source,
deployment files, synthetic samples, SHA256SUMS and source metadata. Failed checks
publish no release. Visitors only need the deployed website URL; the download is
for someone deploying their own copy.

Live Azure quota, managed identity and HTTPS must be verified on a real student
subscription. Regression tests use generated image cases and storage fakes; they
do not establish a production accuracy benchmark.

## License

Original code is [MIT licensed](LICENSE). Dependencies and model weights retain
their own licenses. This is a college teaching project with a single-VM deployment;
maintain backups for important media.
