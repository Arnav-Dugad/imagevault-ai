# Azure for Students deployment

ImageVault can run entirely on Azure: **Ubuntu VM + private Azure Blob Storage**.
The laptop can be switched off. Users open the deployed HTTPS address in a browser.
FastAPI, PostgreSQL/pgvector, Redis, and the CPU AI worker run on the VM; originals
and thumbnails live in Blob Storage. No Azure OpenAI, paid inference API, AKS,
Application Gateway, Azure Container Registry, or managed database is required.

## What “free” means

[Azure for Students](https://azure.microsoft.com/free/students/) currently offers
**$100 credit for 12 months**, with annual renewal while eligible, and selected
free-service allowances. Check your own subscription's offers and remaining credit.
This deployment uses **Standard_B2ms (2 vCPU, 8 GiB RAM)** by default. It is not
the 1 GiB free-tier VM and its compute consumes credit. The existing media and
OpenCLIP pipeline is too large for a 1 GiB machine. B-series CPU credits can also
limit sustained throughput. Use this as a small private/demo deployment, not
an unlimited production photo service.

Before deploying, inspect the regional estimate in the
[Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/).
Include the VM, a **64 GiB Standard SSD**, **Standard public IPv4**, Blob Storage,
transactions, retained deleted blobs, and outbound bandwidth. No fixed monthly
price or year-long free operation is promised. An example monthly alert budget
of $8 is approximately $96/year, but **budgets only notify; they do not cap spend**.

Keep the [student spending limit](https://learn.microsoft.com/azure/cost-management-billing/manage/spending-limit)
enabled and do not upgrade to Pay-As-You-Go if you want to avoid out-of-pocket
cloud charges. Exhausted credit can disable your services. Back up before that
happens. Daily auto-shutdown at **20:00 UTC (01:30 IST)** is created by default;
there is no automatic startup. Deallocating stops compute billing; disks, stored
objects, and public IP can still incur charges. Adjust the schedule in the portal.

## 1. Prepare your student subscription

1. Activate Azure for Students using your college account.
2. Select that subscription in the Azure portal. Check credit and regional quota
   for Standard_B2ms, and verify you can create a Storage account and role assignment.
3. Create a Cost Management budget with alerts for your resource group or subscription.
4. Open **Azure Cloud Shell → Bash**. Alternatively use Azure CLI on Linux/WSL.
   Cloud Shell storage may itself incur usage; an ephemeral session is sufficient.

## 2. Get the release and create an SSH key

Download/extract the latest release or clone the repository:

```bash
git clone https://github.com/Arnav-Dugad/imagevault-ai.git
cd imagevault-ai
ssh-keygen -t ed25519 -f "$HOME/.ssh/imagevault" -C imagevault
```

Keep the private key safe and copy it to your own trusted machine if Cloud Shell
is ephemeral. The deployment only takes the `.pub` file. Do not commit either key.

If using your local CLI, run `az login` and select the student subscription with
`az account set --subscription YOUR_SUBSCRIPTION_ID`. Cloud Shell is already signed in.
The script prints the active subscription so you can verify it before it creates resources.

## 3. Deploy

```bash
bash scripts/deploy_azure.sh imagevault-student centralindia "$HOME/.ssh/imagevault.pub"
```

The script resolves the latest published release, checks its installation archive,
then creates a dedicated resource group and deploys the Bicep template. The VM
downloads that **specific release**, checks SHA-256, generates secrets privately,
and builds/starts containers. The compiled UI in the release avoids a Node build
on the VM. First install can take 15–30 minutes depending on mirrors and VM CPU.
OpenCLIP weights are downloaded separately on the first analysis job.

If your region rejects Standard_B2ms, check available **x64 SKUs with at least
8 GiB RAM** and their price/quota, then set `AZURE_VM_SIZE` before running the script.
Do not choose an ARM VM: this worker's current wheels and container dependencies
target x64. For a reproducible rollout, pass a release tag as the fourth argument.

SSH is restricted to the caller's detected public IP. From Cloud Shell this is
Cloud Shell's IP, not your laptop's IP. Set `SSH_SOURCE_CIDR=YOUR_LAPTOP_IP/32` before
deployment if you want to SSH from your laptop. The script accepts only IPv4 CIDRs
of /24 or narrower. Update the NSG's SSH rule when your public IP changes.

## 4. Open the app

The deployment returns `appUrl` and `sshCommand`. Connect using your private key:

```bash
ssh -i "$HOME/.ssh/imagevault" imagevault@YOUR_RETURNED_HOSTNAME
sudo cloud-init status --wait
sudo tail -n 80 /var/log/cloud-init-output.log
cd /opt/imagevault/app
sudo docker compose -f docker-compose.azure.yml -f docker-compose.download.yml ps
sudo sed -n 's/^REGISTRATION_CODE=//p' .env
```

Treat the invitation code as private. Open the returned **https://** address and
create an account with it. Caddy obtains a certificate for the Azure DNS hostname
automatically; this requires working DNS and inbound ports 80 and 443. No paid domain
is required. Invite only the people whose storage/processing you can support.
Each account has a default **2 GiB original-file quota**, 15 MiB photo uploads,
100 MiB video/RAW uploads, and 10 files per batch. Quotas are application controls,
not Azure billing limits; thumbnails, migrations, soft-deleted blobs and traffic
are additional usage. Every invited account gets its own quota.

The VM identity receives Storage Blob Data Contributor on **this storage account**.
Shared account keys and public blobs are disabled. Gallery URLs use short-lived,
HTTPS-only, read-only user-delegation SAS tokens. Keep SAS URLs private until expiry.
Database, Redis, AI metrics, and management consoles have no public ports.
Prometheus/Grafana are omitted from this small cloud deployment; the authenticated
System page still reports health. Managed identity works through the VM metadata
endpoint from the API and worker containers, with proxy bypass configured.

To close registration after creating accounts, edit `/opt/imagevault/app/.env` and
set `REGISTRATION_ENABLED=false`, then recreate the backend and worker:

```bash
sudo docker compose -f docker-compose.azure.yml -f docker-compose.download.yml up -d backend worker
```

Existing local credentials and app data are **not migrated automatically**.

## Move an existing local vault

1. Stop new uploads and the local worker. Keep PostgreSQL and MinIO running.
2. Back up the local database:
   `docker compose exec -T postgres pg_dump -U imagevault -d imagevault -Fc > imagevault.dump`.
   Use a binary-safe shell (Bash/WSL or PowerShell 7.4+).
3. On the local host, create a Python environment and install `pip install -e ./backend`.
   Sign in with Azure CLI; the signed-in identity needs Storage Blob Data Contributor
   on the new account. Set `MINIO_ENDPOINT=localhost:9000`, MinIO credentials,
   `AZURE_STORAGE_ACCOUNT_URL`, and `AZURE_STORAGE_CONTAINER=imagevault`. Export
   environment variables or use the existing private `.env`.
4. Run `python scripts/migrate_storage.py` for a count/size dry run, then run
   `python scripts/migrate_storage.py --apply`. It streams every original and
   thumbnail, preserves object keys, and verifies SHA-256 for every copied object.
   **Source objects are retained.** Use an empty Azure vault; do not mix two databases.
   Verification adds Blob read transactions and outbound traffic. Interruptions
   can be retried; matching destination keys are overwritten from the frozen source.
5. Stop the cloud backend/worker, securely copy the dump to the VM, and restore it
   into the new empty PostgreSQL database with `pg_restore`. Ensure the `vector`
   extension and original users/IDs are retained. For a new installation:
   `sudo docker compose -f docker-compose.azure.yml exec -T postgres pg_restore -U imagevault -d imagevault --clean --if-exists < imagevault.dump`.
   This overwrites that database, so only use it on your empty destination.
6. Start the cloud stack and verify counts, account login, original downloads,
   previews, and a newly uploaded photo. The new JWT secret means users log in again.
   Run **Settings → Re-analyze library** if needed. Keep the local backup until
   you have verified the Azure copy. Reindex or retry any jobs pending during migration.

## Stop, start, back up, and update

```bash
# Run these in Cloud Shell or your local Azure CLI, not inside the app container.
az vm deallocate -g imagevault-student -n imagevault-vm
az vm start -g imagevault-student -n imagevault-vm
```

Persistent volumes on the VM's OS disk retain PostgreSQL, Redis, model weights,
and certificates across deallocation. Blob Storage retains original media.
For backups, export PostgreSQL with `pg_dump` and keep an independent copy of
Blob Storage. Blob soft delete keeps deleted objects/containers for seven days
but does not back up PostgreSQL and is not a substitute for a full backup.

For upgrades, back up first, stop backend/worker, and extract a checksum-verified
new release into the existing `/opt/imagevault/app` directory, preserving `.env`
and Docker volumes. Update `APP_VERSION` to the release's version, then run:

```bash
sudo docker compose -f docker-compose.azure.yml -f docker-compose.download.yml up -d --build
```

The API applies Alembic migrations at startup. Old binary rollback may require
restoring the database backup. Bootstrap/cloud-init is for initial deployment;
redeploying Bicep does not update existing application files automatically.

## Troubleshooting

- **Quota/SKU failure:** try a permitted region/8 GiB x64 SKU; inspect Azure's price first.
- **Storage 403:** allow time for RBAC propagation, inspect role assignment,
  and test VM managed-identity access. Never make the container public to fix it.
- **Cloud-init failure:** inspect `/var/log/cloud-init-output.log`; after correcting
  the issue, `sudo /usr/local/sbin/imagevault-bootstrap` retries without replacing `.env`.
- **No HTTPS:** check Azure DNS, NSG ports 80/443, and Caddy logs.
- **AI pending:** inspect worker logs. Model downloads need outbound internet;
  B-series CPU throttling can make analysis slow. The app does not include a GPU.
- **Storage limit:** delete unwanted media, or carefully change the quota in `.env`;
  retained deleted blobs can still use credit for seven days.
- **Services stop at night:** the daily shutdown is intentional; start the VM in Azure.

## Releases

Every successful `main` CI run publishes an immutable
`vVERSION-build.RUN_NUMBER` release with ZIP, TAR.GZ, SHA256SUMS, and source metadata.
Failed checks publish nothing. Re-running the same run uploads to the same release.
Pull requests do not publish. Bump app versions together when making a feature release.
The direct [latest downloads](https://github.com/Arnav-Dugad/imagevault-ai/releases/latest)
link is included in the website's System page and README. These are website/server
bundles for people deploying their own copy; visitors only need a browser.

## Validation boundary

CI validates Python tests, frontend lint/tests/build/audit, both Compose stacks,
container definitions, Bicep compilation, deployment scripts, Kubernetes and Terraform.
Blob provider tests use SDK fakes for private storage behavior and SAS signing.
Live Azure deployment, region quota, certificate issuance, and managed-identity
RBAC require a real student subscription and must be verified after deployment.
