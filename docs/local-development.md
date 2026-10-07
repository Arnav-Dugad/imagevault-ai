# Optional local development and course extensions

Updated 7 October 2026 for application 1.2.1. The primary website is
[Azure](azure-students.md); [Windows setup](setup-windows.md) covers both paths.
Local development uses MinIO, Nginx and Prometheus/Grafana.

## Windows Docker startup

Install/start Docker Desktop with WSL2 and Linux containers. Recommended host:
16 GiB RAM, about 10–12 GiB available to Docker and adequate free disk for models,
builds and uploaded data. From the repository root:

```powershell
if (-not (Test-Path .env)) { powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_env.ps1 }
powershell -ExecutionPolicy Bypass -File .\scripts\start_imagevault.ps1 -CpuOnly
docker compose ps
docker compose logs --tail=80 backend worker
```

Preserve an existing `.env`; do not force-regenerate secrets. On Linux/macOS,
copy `.env.example`, replace all placeholders, then `docker compose up -d --build`.
The startup script can attempt optional NVIDIA acceleration without `-CpuOnly`;
CPU is sufficient for the supported path.

| Surface | URL |
|---|---|
| App / API docs | `http://localhost` / `http://localhost/docs` |
| MinIO console | `http://localhost:9001` |
| Grafana | `http://localhost:3001` |
| Prometheus | `http://localhost:9090` |

Use private environment credentials for MinIO/Grafana; app accounts are registered
in the browser. First model analysis downloads cached weights. Upgrade an older
library with **Duplicate review → Upgrade smart index** for analysis version 6.
Stop with `docker compose down`; `down -v` deletes persistent volumes.

Release bundles can use the precompiled frontend:

```powershell
docker compose -f docker-compose.yml -f docker-compose.download.yml up -d --build
```

Do not merge Azure and local Compose files. Changing storage provider alone does
not migrate accounts/metadata/objects. See [Azure migration](azure-students.md#move-an-existing-local-vault).

## Focused application development and tests

Use standalone Python 3.12 (supported range 3.11–3.13) and Node 22, the CI baseline.
See [testing.md](testing.md) for PowerShell and Bash test commands. Worker inference
requires extra model/media dependencies provided by `backend/Dockerfile.worker`;
the test environment uses deterministic substitutes for heavy models.

Vite proxies API/health/metrics to `localhost:8000`. Running `uvicorn` alone still
requires reachable PostgreSQL, Redis and object storage. Docker service names
such as `postgres` and `minio` are not hostnames on Windows; use host port mappings
and matching environment settings for any host-run components.

## Optional Minikube/Kubernetes

Only use this for an orchestration rubric or separate local rehearsal:

```powershell
minikube start --cpus=4 --memory=10240 --disk-size=30g
minikube image build -t imagevault/backend:local -f backend/Dockerfile backend
minikube image build -t imagevault/worker:local -f backend/Dockerfile.worker backend
minikube image build -t imagevault/frontend:local -f frontend/Dockerfile frontend
kubectl apply -f infra/kubernetes/namespace.yaml
Copy-Item infra/kubernetes/secret.yaml.example infra/kubernetes/secret.yaml
```

On subsequent runs, preserve an existing private Secret file. Replace placeholders
in the ignored `secret.yaml`, then:

```powershell
kubectl apply -f infra/kubernetes/secret.yaml
kubectl apply -k infra/kubernetes
kubectl get pods -n imagevault
minikube service imagevault-gateway -n imagevault --url
```

Set `MINIO_PUBLIC_ENDPOINT` in `config.yaml` to the browser-reachable MinIO API
host/port when it differs from the example. For a scaling demonstration:

```powershell
kubectl scale deployment imagevault-backend -n imagevault --replicas=3
minikube addons enable metrics-server
kubectl apply -f infra/kubernetes/hpa-optional.yaml
kubectl get hpa -n imagevault
```

## Optional local Terraform

Terraform targets the chosen local Kubernetes context, not Azure:

```powershell
Set-Location infra/terraform
Copy-Item terraform.tfvars.example terraform.tfvars
# Replace private placeholders and verify the Kubernetes context before apply.
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan
terraform apply
```

Preserve an existing private variables file. Do not let Terraform and manual
`kubectl` independently own the same resources. Review any destroy plan carefully:
removing persistent volumes can remove data. Local monitoring configuration is
in `infra/prometheus` and `infra/grafana`; these tools are not installed by the
primary Azure Compose deployment.