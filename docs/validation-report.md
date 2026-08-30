# Validation report

## Executed in this workspace

| Check | Result |
|---|---|
| Frontend exact dependency install | Passed; lockfile generated |
| npm security audit | Passed; 0 known vulnerabilities reported after upgrades |
| TypeScript production build | Passed with Vite; route-level code splitting produced separate product pages |
| ESLint | Passed with zero warnings |
| Vitest | Passed: 1 file, 2 tests |
| Backend static analysis | Passed with Pyright: 0 errors, 0 warnings |
| Kubernetes, Compose, CI, Prometheus and Grafana YAML parse | Passed |
| Grafana dashboards and project JSON parse | Passed |
| PowerShell secret/environment bootstrap | Passed on Windows PowerShell; temporary validation file removed |
| Git ignore checks | `node_modules`, `dist`, `.env`, state, caches, uploads, volumes and model weights are excluded |
| Social preview | Generated once, spelling inspected, saved as `frontend/public/og.png`, and included in the successful build |

## Implemented tests awaiting a Python runtime

The backend pytest suite contains 19 test functions covering registration/login, duplicate accounts, protected routes, liveness, validated upload, exact SHA-256 duplicates, same-batch grouping, smart reindex queueing, cross-user isolation, corrupt files, MIME/content mismatch, vector normalization, similarity labels, multi-hash consensus, multi-signal evidence gates, worker loop reuse, and thumbnail output. Some test functions contain multiple assertions; the precise assertion-level evidence is recorded by pytest in the target environment.

## Not executable in this workspace

The current host exposes Node/npm and Git but not Python, Docker, kubectl, Minikube, or Terraform. Therefore the following results are not fabricated:

- Ruff and pytest execution.
- Alembic migration against PostgreSQL/pgvector.
- Docker image builds or a complete Compose health run.
- First OpenCLIP model download and CPU/CUDA inference.
- MinIO signed browser previews and object cleanup.
- Minikube scheduling, probes, PVCs, NodePorts, manual scaling, and optional HPA.
- Terraform init/validate/plan/apply.
- Prometheus scrapes and live Grafana panels.

The GitHub Actions workflow performs Python/Ruff/pytest, frontend, Compose/Dockerfile, Kubernetes render, and Terraform static validation on a compatible runner. Full stateful and AI integration remains a documented manual gate on the student’s Docker Desktop/Minikube machine.

## Required final acceptance commands

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_env.ps1
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 backend worker

cd backend
ruff check app tests
pytest -q

cd ..\frontend
npm ci
npm audit --audit-level=moderate
npm run lint
npm test
npm run build

cd ..\infra\terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

Then follow `docs/demo-script.md`, capture only real screenshots/results, and fill the marked academic placeholders.
