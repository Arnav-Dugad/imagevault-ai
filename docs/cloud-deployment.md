# Student cloud deployment

ImageVault supports private Azure Blob Storage, AWS S3, and the original local MinIO deployment. Choose **Azure** if you already have Azure for Students. The same upload, thumbnail, duplicate, search, and deletion flows use the selected provider. AI inference remains self-hosted; there is no paid AI API.

## Choose where processing runs

| Mode | Where files live | Where app, PostgreSQL, Redis and AI run | Laptop can be off? |
|---|---|---|---|
| Hybrid, lowest cloud cost | Azure Blob or S3 | Your laptop with Docker | No |
| Fully hosted demo | Azure Blob or S3 | One Linux VM with Docker | Yes, while VM runs |
| Original local mode | MinIO | Your laptop | No |

The cloud Compose file is standalone. Do **not** combine it with `docker-compose.yml`. It omits MinIO and monitoring servers, binds the gateway to localhost, rotates container logs, uses one CPU worker, and persists PostgreSQL, Redis and model weights in volumes. It does not provision infrastructure on startup.

Use a fresh installation for an initial demo. Existing media requires the migration steps below; changing an environment variable alone does not copy objects or accounts.

## 1. Check your credits first

In Azure Portal, open **Subscriptions → Azure for Students**. Check its actual remaining credit, expiry, region restrictions and VM quota. Keep its spending limit enabled. Add a monthly Cost Management budget suitable for your remaining credit, with email alerts at 50%, 80% and 100%; a budget alert is not a hard spending cap.

The published Azure for Students offer includes $100 to use within 12 months, subject to eligibility. Your remaining balance may be lower. Do not assume this stack is covered by the smallest free VM allowance. AWS's current free plan/credits differ from Azure and from AWS Educate classroom access; check your own account's Billing page before choosing it.

## 2. Create private Azure storage

In Azure Portal create a dedicated resource group, for example `imagevault-student`, in a region your subscription allows. Create a **Storage account**:

- Globally unique name, Standard performance, locally redundant storage (LRS), Hot access tier.
- Secure transfer required; minimum TLS 1.2; anonymous blob access disabled.
- Create container `imagevault` with **Private (no anonymous access)**.
- Enable seven days of blob/container soft delete. Retained deleted objects continue to count toward storage charges.
- Use the normal public HTTPS endpoint for signed browser previews. Private networking is a separate setup requiring browser/network access; do not enable a private endpoint for this basic recipe.

Alternatively the included Bicep file creates these storage resources. In Azure Cloud Shell (Bash), upload `infra/cloud/storage.bicep`, select the correct subscription, and review before creating:

```bash
az account set --subscription 'YOUR_SUBSCRIPTION_ID'
az group create --name imagevault-student --location eastasia
az deployment group what-if --resource-group imagevault-student \
  --template-file storage.bicep --parameters storageAccountName=YOUR_UNIQUE_NAME
az deployment group create --resource-group imagevault-student \
  --template-file storage.bicep --parameters storageAccountName=YOUR_UNIQUE_NAME
```

`eastasia` is an example, not a guarantee of regional availability. Bicep creates storage only; it does not create a VM or automatically grant runtime identity permissions.

## 3. Configure ImageVault

Install Git and Docker with Compose v2. Clone your private repository using GitHub's normal authenticated Git flow; never put a token in the clone URL.

```bash
git clone https://github.com/Arnav-Dugad/imagevault-ai.git
cd imagevault-ai
cp .env.cloud.example .env.cloud
```

On Windows PowerShell use `Copy-Item .env.cloud.example .env.cloud`. Generate two independent secrets (run this command twice):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set one as `POSTGRES_PASSWORD` and use **the same password** in `DATABASE_URL`. Set the other as `JWT_SECRET`. The hex format avoids URL-escaping problems in the database connection string. Keep `.env.cloud` private (Linux: `chmod 600 .env.cloud`). Never commit it, post it in chat, or include it in screenshots.

Set `STORAGE_PROVIDER=azure`, the actual `AZURE_STORAGE_ACCOUNT_URL`, and `AZURE_STORAGE_CONTAINER=imagevault`.

**Laptop/hybrid authentication:** copy the connection string from your dedicated storage account's **Access keys** into `AZURE_STORAGE_CONNECTION_STRING`. It must include `AccountKey` and use HTTPS. This key grants broad access to that storage account, so use an account dedicated to this project and rotate it if exposed. Keep it server-side only.

**Azure VM authentication (preferred):** enable the VM's system-assigned managed identity. At the storage account's **Access control (IAM)**, grant that identity **Storage Blob Data Contributor** at the storage-account scope. This scope allows both blob operations and creation of user-delegation keys for read-only preview links. Leave the connection string empty. Allow a few minutes for role propagation. The containers must be able to reach Azure's instance metadata endpoint. No Azure CLI login inside the containers is needed. You can disable Shared Key access on the storage account when all clients use managed identity.

## 4. Start privately and create your account

Temporarily set `REGISTRATION_ENABLED=true` in `.env.cloud` while the app is only reachable through localhost/SSH. Start:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d --build
docker compose --env-file .env.cloud -f docker-compose.cloud.yml ps
```

Open `http://localhost:8080`. On a remote VM first open an SSH tunnel from your laptop:

```bash
ssh -L 8080:127.0.0.1:8080 azureuser@YOUR_VM_IP
```

Register your account, then set `REGISTRATION_ENABLED=false` and apply it:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d backend worker
```

Existing users can still log in; new registrations receive an explicit closed-registration error. The UI retains the registration tab but the API enforces this policy.

Upload a small JPG, wait for processing, open its thumbnail/original, check **System status**, test search, and delete a disposable image. Verify the objects in the private cloud container. Signed previews should work; removing the signature from their URL should deny access. First inference downloads model weights and can take several minutes.

## 5. Run without your laptop (optional VM)

Create an Ubuntu 24.04 LTS **x86-64** VM in the same region as storage. Start with **4 vCPU / 16 GiB RAM**, and around **64 GiB Standard SSD** disk for the images, build cache and database. This is a conservative demo starting point, not a benchmark or a free-tier claim. The full worker includes OpenCLIP, face models, OCR, RAW and video decoding; tiny 1–2 GiB free VMs are not suitable. A lower-memory VM needs measurement against your workload. Select an available size and inspect its current estimated price before creating it.

Use SSH-key login, allow SSH only from your current public IP, and install Docker Engine + Compose using Docker's Ubuntu instructions. Transfer/clone the repository, configure managed identity, then follow steps 3–4 on the VM. The SSH tunnel is enough for a private college demo and needs no domain.

For public HTTPS access:

1. Point a DNS name you control to the VM's public IP (an Azure public-IP DNS label can also be used).
2. Set `PUBLIC_HOSTNAME` to that hostname without a scheme, and `CORS_ORIGINS=https://YOUR_HOSTNAME`.
3. Keep registration closed. Allow inbound TCP 80 and 443 in the VM's network security group.
4. Start the TLS override, which uses Caddy to obtain/renew a certificate:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml \
  -f docker-compose.cloud-tls.yml up -d --build
```

Ports for PostgreSQL, Redis, the API and worker are not published. The public TLS gateway blocks `/metrics`, `/docs`, `/redoc` and `/openapi.json`. Use exactly the same Compose file arguments for subsequent updates/down commands. This remains a single-VM demo, not a highly available service.

## AWS S3 alternative

Create a dedicated S3 bucket in your chosen region with **Block all public access** enabled, ACLs disabled (bucket-owner-enforced), and default server-side encryption. No public bucket policy or public ACL is needed for signed previews.

Set `STORAGE_PROVIDER=s3`, `S3_BUCKET`, and `S3_REGION` in `.env.cloud`. Prefer an EC2 instance role; grant only the permissions in `infra/cloud/s3-policy.example.json`, replacing `REPLACE_BUCKET`. If running Docker on EC2 with IMDSv2, configure the metadata response hop limit for container access (typically 2); keep IMDSv2 required. For a local demo, use scoped temporary credentials in `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`; refresh them when they expire. Never use root credentials. Standard AWS SDK credential resolution is used; the Compose file does not mount your host's AWS config/SSO files.

The same cloud Compose and TLS steps apply. AWS Educate labs may restrict IAM, lifetime and services; do not assume those lab credits are an unrestricted long-lived hosting account. AWS support here is the storage adapter and portable VM recipe, not automated AWS infrastructure provisioning.

## Existing-data migration and backup

The database contains accounts, ownership, object keys, thumbnails, vectors and duplicate links. Both database and objects must move together. There is one active storage provider per deployment, so perform a coordinated cutover:

1. Back up the existing database and MinIO volume first. Stop the old gateway/backend/worker so neither uploads, deletes nor worker writes can occur during copying. Leave PostgreSQL and MinIO running for export.
2. Export the complete MinIO bucket using MinIO Client (`mc mirror source/imagevault ./imagevault-export`). Preserve every relative object key, including generated thumbnails. Treat the export directory as private.
3. Upload the export using Azure CLI (`az storage blob upload-batch --account-name YOUR_ACCOUNT --destination imagevault --source ./imagevault-export --auth-mode login`) or AWS CLI (`aws s3 sync ./imagevault-export s3://YOUR_BUCKET`). Use an initially empty destination. Your Azure CLI identity needs Blob Data Contributor. Commands transfer data and can consume bandwidth credits.
4. Independently verify object count, total bytes, and SHA-256 of downloaded samples, including originals and thumbnails. For valuable collections verify all object hashes. Do not infer byte equality from an S3 multipart ETag.
5. Export PostgreSQL with `pg_dump -Fc` and restore it into the cloud stack's PostgreSQL **before starting the backend/worker**. The cloud stack uses separate volumes and does not automatically import the old database. Use the same PostgreSQL major version (16); install/retain pgvector. Review `pg_restore` output for errors.
6. Start the cloud app, log in using an existing account, and verify old/new images, signed previews, AI processing, search and deletion of a disposable copy. Old JWTs may stop working after changing the JWT secret; log in again.
7. Keep the old database and objects until the new installation is verified. Roll back by stopping the cloud stack and restarting the old stack. New writes after cutover would need to be copied back before rollback; do not run both writable copies concurrently.

Example Linux database backup from the old stack (run before stopping PostgreSQL):

```bash
mkdir -p .cloud-backup
chmod 700 .cloud-backup
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > .cloud-backup/imagevault.dump
```

Example restore into a **new, empty** cloud database, with only PostgreSQL running:

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d postgres
docker compose --env-file .env.cloud -f docker-compose.cloud.yml exec -T postgres \
  sh -c 'pg_restore --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < .cloud-backup/imagevault.dump
```

Use Linux/WSL for these binary redirections (Windows PowerShell 5 can corrupt binary output). Store an encrypted copy outside the VM. Never run a destructive restore over a populated database without a reviewed recovery plan. Back up the database regularly and verify restores; Azure blob soft delete does not back up PostgreSQL.

## Stop costs after a demo

Stop the cloud Compose stack gracefully before deallocating the VM; allow an active upload/job to finish. `docker compose down` preserves named volumes unless `--volumes` is explicitly passed. Do not use `down --volumes` for normal shutdown.

In Azure Portal stop the VM and verify **Stopped (deallocated)**, or use:

```bash
az vm deallocate --resource-group imagevault-student --name YOUR_VM_NAME
```

An OS shutdown alone can leave the VM allocated and billed. Disks, stored blobs, soft-deleted data, public IPs and network usage can still incur charges while compute is deallocated. Configure daily VM auto-shutdown as a backup measure and verify the resulting state. Delete dedicated resources only after exporting required data.

Estimate credit lifetime from your account's actual prices:

`monthly cost ≈ VM hourly price × running hours + disks + object GB-months + operations + outbound transfer + IP charges`

`credit runway ≈ remaining credit / estimated monthly cost`, capped by credit expiry.

Keeping processing on your laptop avoids the cloud VM charge. Cloud storage still has storage/transaction/egress costs. No indefinite zero-cost hosting claim is made.

## Troubleshooting

- **Azure authorization error:** check the selected identity, account-scope Blob Data Contributor assignment and propagation; connection-string mode needs AccountKey for preview signing.
- **Previews fail but upload works:** check browser access to the blob endpoint, system clock, signing permission and SAS expiry. Do not make the container public.
- **S3 preview 403:** check bucket region, role policy and credential expiration. A temporary credential can expire before the link's configured TTL.
- **Production configuration error:** replace the JWT placeholder with a random secret and disable debug.
- **Image remains pending:** inspect backend and worker logs, Redis memory and worker heartbeat. Redis now refuses new writes rather than silently evicting queued jobs when full; resolve memory pressure and use Settings → Re-analyze all after recovery.
- **Build/AI worker fails on a tiny VM:** check `docker stats`, free disk and memory. Increase RAM or use hybrid mode. Burstable VM CPU credits can also slow prolonged inference.

## References

- [Azure for Students](https://azure.microsoft.com/en-us/free/students/)
- [Azure spending limits](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit)
- [VM states and billing](https://learn.microsoft.com/en-us/azure/virtual-machines/states-billing)
- [Azure user-delegation SAS](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-user-delegation-sas-create-python)
- [AWS free tier](https://aws.amazon.com/free/)
- [S3 presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
