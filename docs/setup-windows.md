# Run ImageVault AI from Windows and connect Azure

Updated 7 October 2026 for application 1.2.1, GitHub main commit `9ee8c0c`.
This folder contains the updated source and your existing private local `.env`.
Azure has not been deployed or connected by this update.

## Choose where it runs

| Option | What you install on your PC | Where the app and data run |
|---|---|---|
| Azure website (primary) | Azure CLI and Windows OpenSSH | Five containers on an Ubuntu VM; private media in Azure Blob Storage |
| Local demo (optional) | Docker Desktop with Linux containers | Containers and MinIO on this PC |

Azure CLI is already installed on this PC. Docker Desktop and a standalone
project-compatible Python were not found on PATH during this update. Neither
is needed on your PC for the Azure deployment. The Azure CLI's bundled Python
is for Azure CLI itself; do not use it as the backend development environment.

## 1. Activate Azure for Students

1. Visit [Azure for Students](https://azure.microsoft.com/free/students/), sign in
   with your Microsoft account and complete academic eligibility verification.
2. Open [Azure Portal](https://portal.azure.com), search **Subscriptions**, and
   confirm **Azure for Students** is active. Record its subscription ID privately.
3. Check remaining credit and keep the subscription spending limit enabled.
   The current offer provides USD $100 for the first 12 months without a credit
   card at signup; eligibility, renewal and allowances depend on Microsoft's terms.
4. Check **Usage + quotas** for the intended region and the VM size. This template
   uses `Standard_B2ms`, an x64 CPU VM with 2 vCPU and 8 GiB RAM. It uses credit;
   it is not the small free-tier VM. Check VM, disk, IP, storage and traffic costs
   in the [pricing calculator](https://azure.microsoft.com/pricing/calculator/).
5. In **Cost Management → Budgets**, create a budget with alerts appropriate to
   your remaining credit. Alerts notify you; they do not stop resources.

You need permission to create resources and assign the VM's storage role. If a
college-managed subscription denies role assignments, ask its administrator.

## 2. Open PowerShell in this folder and sign in

Use a normal PowerShell window under your Windows user account:

```powershell
Set-Location 'C:\Users\rduga\Desktop\ImageVault AI - CCD project'
az version
ssh -V
az login
az account list --output table
az account set --subscription 'YOUR_STUDENT_SUBSCRIPTION_ID'
az account show --query '{Name:name,ID:id,State:state}' --output table
```

Replace `YOUR_STUDENT_SUBSCRIPTION_ID` with your actual ID. `az login` opens a
browser. If that flow fails, use `az login --use-device-code` and follow its
instructions yourself. Do not put tokens, passwords or subscription credentials
in the repository or chat.

If `az` is missing on another PC, install it with
`winget install --exact --id Microsoft.AzureCLI`, then reopen PowerShell. If
`ssh` is missing, install **OpenSSH Client** under Windows **Optional features**.

## 3. Generate a dedicated SSH key

```powershell
$sshKeyPath = Join-Path $env:USERPROFILE '.ssh\imagevault'
New-Item -ItemType Directory -Force (Split-Path -Parent $sshKeyPath) | Out-Null
ssh-keygen -t rsa -b 4096 -f $sshKeyPath -C imagevault
```

Choose a passphrase and retain it. If that path already contains a key, reuse it
or choose another name; do not overwrite it. The `.pub` file is the public key.
The file without `.pub` is the private key and stays on your PC.

## 4. Prepare deployment parameters

Run in the same PowerShell window:

```powershell
$resourceGroup = 'imagevault-student'
$azureRegion = 'centralindia'
$vmSize = 'Standard_B2ms'
$release = Invoke-RestMethod 'https://api.github.com/repos/Arnav-Dugad/imagevault-ai/releases/latest'
$releaseTag = $release.tag_name
$releaseTag
$publicIp = (Invoke-RestMethod 'https://api.ipify.org').Trim()
if ($publicIp -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw 'An IPv4 address is required for the SSH rule.' }
$publicKey = (Get-Content -Raw -LiteralPath "$sshKeyPath.pub").Trim()
if ($publicKey -notmatch '^ssh-(rsa|ed25519) ') { throw 'Use an OpenSSH public key.' }
if ($releaseTag -notmatch '^v\d+\.\d+\.\d+(-build\.\d+)?$') { throw 'Unexpected release tag.' }
New-Item -ItemType Directory -Force .\tmp | Out-Null
$deploymentParameters = @{
    '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion = '1.0.0.0'
    parameters = @{
        location = @{ value = $azureRegion }
        vmSize = @{ value = $vmSize }
        sshPublicKey = @{ value = $publicKey }
        sshSourceCidr = @{ value = "$publicIp/32" }
        releaseTag = @{ value = $releaseTag }
    }
}
$parametersPath = Join-Path (Get-Location) 'tmp\azure-parameters.json'
[System.IO.File]::WriteAllText($parametersPath, ($deploymentParameters | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
az bicep install
```

The ignored `tmp` file contains public deployment parameters, not a storage key.
The VM installs that published release with a checksum check. Your local docs
edits are not uploaded by Bicep. To pin a particular published version, set
`$releaseTag` before building the parameters. The latest stable release verified
for this update is recorded in [validation-report.md](validation-report.md).

`centralindia` is a starting choice, not an availability guarantee. If Azure
rejects the region or SKU, choose one your student subscription allows with
**x64 and at least 8 GiB RAM**, compare its price, and rebuild the parameters.

## 5. Review, then create the Azure resources

These commands create resources that consume student credit:

```powershell
az group create --name $resourceGroup --location $azureRegion --output table
az deployment group what-if --resource-group $resourceGroup --template-file .\infra\azure\main.bicep --parameters "@$parametersPath"
az deployment group create --resource-group $resourceGroup --name imagevault --template-file .\infra\azure\main.bicep --parameters "@$parametersPath" --query properties.outputs --output json
```

The template creates the VM, 64 GiB OS disk, network, restricted SSH rule, static
public IP/DNS name, private Storage account/container, managed identity, storage
role assignment and daily shutdown. It then installs Docker and the app on the VM.
Resource provisioning success does not mean the app build has finished.

If Azure reports `MissingSubscriptionRegistration`, register only the provider
named in the error with `az provider register --namespace PROVIDER_NAME --wait`,
then retry. For a permission error assigning storage access, resolve permissions
instead of enabling public blobs or account keys.

## 6. Wait for installation on the VM

```powershell
$appUrl = az deployment group show --resource-group $resourceGroup --name imagevault --query properties.outputs.appUrl.value --output tsv
$appHost = ([Uri]$appUrl).Host
ssh -i $sshKeyPath "imagevault@$appHost"
```

Check the host fingerprint through a trusted channel before accepting it.
You are now in **Linux on the VM**. Run the following there, not in PowerShell:

```bash
sudo cloud-init status --wait
sudo tail -n 80 /var/log/cloud-init-output.log
cd /opt/imagevault/app
sudo docker compose -f docker-compose.azure.yml -f docker-compose.azure-download.yml ps
sudo docker compose -f docker-compose.azure.yml -f docker-compose.azure-download.yml logs --tail=80 backend worker caddy
sudo sed -n 's/^REGISTRATION_CODE=//p' .env
```

Expect a long first build; the guide estimates 15–30 minutes, but mirrors and VM
CPU can make it longer. Keep the returned invitation code private. Use `exit`
to return to your PC's PowerShell.

## 7. Open and verify the website

1. Open the returned `https://...cloudapp.azure.com` address. Caddy obtains HTTPS
   automatically when DNS and ports 80/443 work.
2. Choose registration, enter your details and the invitation code, then sign in.
3. Open **Advanced → System status**. Check that environment is Azure, storage is
   Azure Blob, and API, database, storage and worker respond.
4. Upload one disposable photo. Wait for its thumbnail and analysis; OpenCLIP
   downloads weights on the first relevant job, so this may take several minutes.
5. Upload an unchanged copy. Confirm SHA-256 exact-copy evidence, open the original
   preview, and try duplicate cleanup with its confirmation dialog.
6. In Azure Portal, open the generated `iv...` Storage account → **Containers →
   imagevault** and verify that objects appeared. The container must stay private.
7. Refresh and sign in again to verify persistence. Rehearse
   [the classroom demo](demo-script.md) before presenting.

The template connects Azure automatically: `configure_azure.py` writes a separate
private `.env` on the VM, cloud Compose selects `STORAGE_BACKEND=azure`, and
`DefaultAzureCredential` obtains the VM identity token. The identity receives
**Storage Blob Data Contributor** at storage-account scope, including the
permission needed for user-delegation SAS previews. No storage connection string,
access key or Azure OpenAI key is required. Your PC's old `.env` is for local MinIO.

Cloud defaults are 2 GiB originals per account, 15 MiB per photo, 100 MiB per
video/RAW upload, and 10 files per batch. These are app quotas, not billing caps.
Existing local accounts/photos are not moved automatically; use the dedicated
[migration procedure](azure-students.md#move-an-existing-local-vault) if needed.

## 8. Start and stop it between demos

Run on your PC, after Azure login:

```powershell
az vm deallocate --resource-group imagevault-student --name imagevault-vm
az vm start --resource-group imagevault-student --name imagevault-vm
az vm get-instance-view --resource-group imagevault-student --name imagevault-vm --query instanceView.statuses --output table
```

Daily shutdown is **20:00 UTC / 01:30 IST the next day**, with no automatic startup.
Deallocation stops compute billing; disk, public IP and Blob charges can continue.
Use Cost Management to check usage. Back up PostgreSQL and media separately.

To close signup after creating accounts, SSH into the VM, edit
`/opt/imagevault/app/.env` with `sudo nano .env`, set
`REGISTRATION_ENABLED=false`, and recreate backend/worker with the same Azure
Compose files. Existing logins continue to work.

## Optional: run on this Windows PC

This is the local MinIO version and needs no Azure subscription.

1. Install Docker Desktop, enable WSL2 and Linux containers, and start Docker.
   Allow approximately 10–12 GiB memory and sufficient disk for images and models.
2. Open PowerShell in this folder. **Your `.env` already exists; preserve it.**
   On a fresh copy only, generate it with `bootstrap_env.ps1`.
3. Start and inspect:

```powershell
Set-Location 'C:\Users\rduga\Desktop\ImageVault AI - CCD project'
if (-not (Test-Path .env)) { powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_env.ps1 }
powershell -ExecutionPolicy Bypass -File .\scripts\start_imagevault.ps1 -CpuOnly
docker compose ps
docker compose logs --tail=80 backend worker
```

4. Open `http://localhost`, register and upload a disposable image. Local signup
   normally needs no invite. Monitoring is at `http://localhost:3001` (Grafana)
   and `http://localhost:9090` (Prometheus); MinIO console is at port 9001.
5. After upgrading an existing vault, use **Duplicate review → Upgrade smart index**
   and wait for analysis version 6. Stop with `docker compose down`; omit `-v`
   to preserve volumes.

Do not combine local and Azure Compose files. Setting an Azure URL in the old
local `.env` alone does not enable VM managed identity on your PC.

## Troubleshooting

| Symptom | Next check |
|---|---|
| Azure CLI cannot list subscriptions | Finish student activation, use the right account/tenant, run `az login` again |
| VM SKU/quota/policy error | Check permitted regions and 8 GiB x64 SKUs, price and quota |
| SSH timeout | Ensure VM is running; update NSG `ssh` source to your current public IPv4 `/32` if it changed |
| Cloud-init fails | Read cloud-init output; correct the cause, then retry `sudo /usr/local/sbin/imagevault-bootstrap` |
| Backend storage 403 | Allow RBAC propagation; check VM identity and account-scoped Blob contributor role |
| HTTPS site not ready | Check cloud-init, backend readiness, Caddy logs, DNS and inbound 80/443 |
| Analysis pending/warning | Check worker logs and outbound model downloads; retry smart index after recovery |
| Site goes offline overnight | Start the VM; daily shutdown is intentional |
| Local `docker` command missing | Install/start Docker Desktop or use the Azure path |

Further operations, backups and migration: [Azure guide](azure-students.md).
Official references: [student offer](https://azure.microsoft.com/en-us/pricing/offers/ms-azr-0170p),
[Windows Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows),
[Bicep deployment](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deploy-cli),
and [VM billing states](https://learn.microsoft.com/en-us/azure/virtual-machines/states-billing).
