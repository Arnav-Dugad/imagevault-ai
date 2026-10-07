# ImageVault AI viva guide

Updated 7 October 2026 for the Azure-hosted 1.2.1 project.

## What is the project?

A private browser-based media vault with upload, gallery, duplicate review and analytics. It demonstrates Azure object storage and identity, VM/container deployment, asynchronous processing, infrastructure as code and CI. Advanced OCR, albums and search remain available.

## Where does it run?

The primary website runs on an Azure Ubuntu VM. Five containers provide Caddy/React, FastAPI, Celery, PostgreSQL/pgvector and Redis. Originals/thumbnails are in Azure Blob Storage. Users need only a browser; the laptop can be off while the VM runs.

## What does Azure for Students provide?

The current offer includes USD $100 credit for 12 months and selected free allowances, subject to eligibility and terms. The default 8 GiB Standard_B2ms VM consumes credit. Disks, IP, Blob operations/storage and traffic can cost credit too. Budgets notify; the spending limit controls the credit-funded subscription. It is not unlimited free hosting. See [cost analysis](cost-analysis.md).

## How is Azure connected without keys?

Bicep enables a system-assigned VM identity and grants Storage Blob Data Contributor on the storage account. Azure SDK DefaultAzureCredential obtains identity tokens on the VM. Cloud Compose selects the Azure provider; a generated private VM environment supplies the endpoint/container. No storage connection string or Azure OpenAI key is required.

## Why Azure Blob instead of MinIO?

Azure Blob is the primary managed object store and persists media separately from compute. MinIO implements the optional local S3-compatible development path. A shared storage interface supports both; Blob is not an S3 endpoint and provider/database migration must be explicit.

## Why not put original media in PostgreSQL?

Blob stores binary objects; PostgreSQL provides transactions, ownership, metadata, processing state, hashes, relationships and vector queries. This separates large media from relational workloads.

## How do previews stay private?

The API checks ownership, then creates a short-lived read-only HTTPS user-delegation SAS URL. The container is never public. The URL itself permits access until expiry, so it must stay private.

## What is the difference between exact, near and semantic matches?

SHA-256 equality identifies identical file bytes. Verified near duplicates require multiple hashes, compatible frame/color evidence and aligned pixels at two scales. Semantic CLIP matches identify related content and can include different shots of the same subject. Similarity is not a deletion-safety probability.

## Why must a family have direct evidence for every pair?

A-B and B-C do not prove A-C. Conservative complete-link grouping avoids joining unrelated endpoints through a chain, though it can split related media into smaller families.

## What are embeddings and pgvector?

OpenCLIP encodes image content as normalized 512-number vectors. pgvector adds vector columns/distance operators and indexes to PostgreSQL. Cosine retrieval finds candidates; it is not sufficient proof of duplication.

## Is Azure AI/OpenAI used?

No hosted inference API is required. OpenCLIP, OCR and face models run inside the self-hosted deployment. On Azure “local inference” refers to the VM, not the presentation laptop. Cloud defaults to CPU.

## Why use Celery and Redis?

They move costly analysis off the upload request and provide tasks, retries and heartbeats. Redis also supports atomic cloud request limits. Kafka would add complexity beyond the small demo workload.

## What happens if models or the queue fail?

Optional model/OCR/face failures preserve successful fingerprints and show warnings. Queue publication failure retains the original and reports retryable analysis. Restore the dependency and use the smart-index action. This is not a fully automatic task outbox.

## What happens if deletion meets a storage outage?

Metadata removal and durable object-deletion records commit together. The API retries storage cleanup every 30 seconds and after restart. Blob deletion is idempotent. Soft-delete retention can keep billed bytes after vault removal.

## How are users isolated?

JWT identifies the active account, and private queries enforce its user ID. Invitation signup and quotas restrict use. Knowing another object's UUID does not authorize access. Different accounts receive separate original-file quotas.

## Why Caddy?

It serves compiled React and obtains HTTPS certificates for the Azure DNS hostname while forwarding API requests. Local development instead uses Nginx; its configuration is a separate deployment path.

## Bicep versus Terraform?

Bicep declares Azure VM, storage, networking, identity/RBAC and shutdown. Docker Compose runs the application. The existing Terraform directory manages the optional local Kubernetes cluster; it does not provision the primary Azure environment.

## Are Kubernetes and Grafana used by the Azure website?

No. The main deployment uses Compose and Bicep with System status/container logs. Minikube/Kubernetes, local Terraform, Prometheus and Grafana are optional course extensions. Discuss Deployments, Services, Secrets, PVCs and HPA only when showing that extension.

## What do liveness and readiness mean?

Liveness checks that the API process responds. Readiness checks required database/object-store access; status additionally reports worker heartbeat/queue/model state. Readiness is not a complete end-to-end application test.

## What does CI/CD do?

GitHub Actions validates Python, frontend, browser fixtures and infrastructure. Passing main builds publish compiled website/server bundles and checksums. Cloud-init installs a selected release. CI does not automatically deploy updates to an already running VM.

## How do you save credit?

Start before demos, deallocate afterwards and check actual usage. Scheduled shutdown defaults to 20:00 UTC, 01:30 IST the next day; it does not start the VM. Disk/IP/Blob charges can continue while deallocated. Do not confuse an OS-level shutdown with Azure deallocation.

## What persists and how is it backed up?

PostgreSQL, Redis, weights and Caddy data use VM disk volumes. Blob stores originals/thumbnails. Back up database and media independently. Blob soft delete is not a PostgreSQL backup; deleting the OS disk can lose the database.

## What has been proven?

Separate code/regression evidence from live deployment and real-world accuracy. Browser fixtures and Azure SDK fakes do not prove managed identity, real models or HTTPS. See [validation-report.md](validation-report.md) for this folder. Report measured precision/recall only on an independent labeled corpus.

## What are the main limitations?

Single VM, finite student credit, regional quota, CPU throughput, model mistakes, sampled video analysis, owner-managed backups and no MFA/email recovery. Heavy edits and changed text need full-resolution manual comparison. No cleanup is automatic.