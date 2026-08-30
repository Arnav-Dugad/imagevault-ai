# ImageVault AI live demonstration script

## Before the room opens

1. Run `docker compose up -d --build` early enough for the initial OpenCLIP download.
2. Confirm `docker compose ps` shows healthy application services.
3. Generate the synthetic set with `python scripts/generate_demo_images.py`.
4. Open ImageVault, MinIO, Grafana, Prometheus, the GitHub Actions page, and the Terraform directory in separate tabs.
5. Create or reset the demo account. Do not reset any other user.
6. Upload one non-exact image once so the model is loaded; then clear the demo account if the presentation should start empty.
7. Keep the actual account password and `.env` out of projected terminals.

## Part 1 — application story (4–5 minutes)

1. Register or log in. State: “Authentication is self-hosted; passwords are Argon2 hashes in our PostgreSQL database.”
2. Show the polished empty dashboard, upload call-to-action, and private processing indicator.
3. Open Upload and select all six generated images.
4. Explain the processing order displayed beside the drop zone:
   - file validation;
   - SHA-256 exact lookup;
   - object storage and background job;
   - thumbnail, pHash, OpenCLIP, and pgvector query.
5. Point out the immediate exact match between `01-...original.jpg` and `02-...exact-copy.jpg`. Say: “This is byte equality, not an AI prediction.”
6. Open Gallery and wait for `READY` states. Mention that the HTTP upload returned before AI processing completed.
7. Open the original image detail and show dimensions, object key abstraction, hash, and visual match cards.
8. Open Duplicate Review. Compare the exact copy with resized/compressed/edited candidates. State that thresholds are configurable and advisory.
9. Select a duplicate, show the confirmation dialog and storage estimate, then cancel once to prove deletion is explicit. Optionally delete during the final rehearsal.
10. Return to Dashboard and show updated counts, recoverable exact bytes, activity chart, and service confidence.

## Part 2 — object storage (1 minute)

1. Open the MinIO console at `http://localhost:9001` and sign in with local `.env` credentials.
2. Navigate to the private `imagevault` bucket.
3. Show `users/{uuid}/originals/` and `users/{uuid}/thumbnails/`.
4. Explain that binaries are objects, PostgreSQL holds metadata, and the S3-compatible design could conceptually migrate without using AWS now.

## Part 3 — containers (1 minute)

```powershell
docker compose ps
```

Point to frontend, Nginx, FastAPI, worker, PostgreSQL/pgvector, MinIO, Redis, Prometheus, and Grafana. Explain the private Compose network, volumes, health checks, and the intentionally single AI worker.

## Part 4 — Kubernetes and scaling (2 minutes)

If using the already-deployed Minikube environment:

```powershell
kubectl get pods,svc,pvc -n imagevault
kubectl get deployment imagevault-backend -n imagevault
kubectl scale deployment imagevault-backend -n imagevault --replicas=3
kubectl rollout status deployment/imagevault-backend -n imagevault
kubectl get pods -n imagevault -l app=imagevault-backend
```

Explain ConfigMaps versus Secrets, readiness versus liveness, PVCs, requests/limits, Deployments versus StatefulSets, and why the stateless API can scale while the model worker remains one replica on a laptop.

After the demonstration, return to one replica:

```powershell
kubectl scale deployment imagevault-backend -n imagevault --replicas=1
```

## Part 5 — monitoring (2 minutes)

1. Open the System Status page and show API, PostgreSQL, MinIO, worker, model, pending jobs, and Redis queue.
2. Run small traffic if graphs are quiet:

```powershell
python scripts/generate_load.py --password "YOUR_LOCAL_DEMO_PASSWORD" --iterations 30
```

3. Open the provisioned Grafana dashboard at `http://localhost:3001`.
4. Show request rate, latency, upload/processing counts, exact/similar counts, inference time, and failures.
5. Briefly show the Prometheus targets page. State that metrics contain no filenames, users, image bytes, or credentials.

## Part 6 — CI/CD (1 minute)

Open a successful GitHub Actions run. Explain:

```text
push / pull request
  → backend lint and tests
  → frontend audit, lint, tests and build
  → Compose / Dockerfile checks
  → Kubernetes render
  → Terraform format and validation
```

Do not claim automatic public deployment; the release target is the reproducible local private cloud.

## Part 7 — Infrastructure as Code (1 minute)

```powershell
cd infra/terraform
terraform fmt -check -recursive
terraform validate
terraform plan
```

Show that only local Kubernetes/kubectl providers exist. Explain declarative desired state and why the plan is reviewed before apply/destroy.

## Closing statement

“ImageVault AI is the application workload. The core project contribution is the complete private-cloud and DevOps lifecycle: objects, database and vectors, asynchronous services, containers, orchestration, Infrastructure as Code, CI validation, health checks, logs, and monitoring—all locally controlled and with no additional cloud bill.”

## Evidence checklist after the final rehearsal

- `[ ] Dashboard screenshot`
- `[ ] Exact duplicate evidence screenshot`
- `[ ] Visual match evidence screenshot`
- `[ ] MinIO object hierarchy screenshot`
- `[ ] Docker Compose services screenshot`
- `[ ] Kubernetes pods/PVCs screenshot`
- `[ ] Grafana dashboard screenshot`
- `[ ] Successful CI run screenshot`
- `[ ] Terraform validate/plan screenshot`
- `[ ] Actual benchmark and test output`
