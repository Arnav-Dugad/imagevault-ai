# ImageVault AI implementation and completion plan

Updated 7 October 2026 for the Azure-based 1.2.1 project.

## Intended outcome

Deliver a browser-based private media vault on Azure for Students using an Ubuntu VM, private Blob Storage, managed identity, Caddy HTTPS, Docker Compose and Bicep. The AI workload demonstrates cloud storage, background processing, identity, CI and operations. Student credit funds resources; unlimited free operation is not assumed.

## Present in the repository

| Area | Implemented artifacts |
|---|---|
| Product | Upload, Gallery, Duplicate review, Dashboard and advanced albums/status/settings |
| Data and auth | PostgreSQL/pgvector, Alembic, Argon2/JWT, invitations and ownership filters |
| Intelligence | SHA-256, multiple hashes, pixel verification, semantic retrieval and optional enrichment |
| Reliability | Warnings/reindex, failed queue reporting, transaction-backed object cleanup |
| Azure | Bicep, cloud-init, managed identity, private Blob, Caddy, quotas/limits and shutdown |
| Delivery | GitHub Actions tests/checks, compiled frontend and checksum-verified releases |
| Optional extensions | Local MinIO/Nginx, Kubernetes/Minikube, local Terraform and monitoring |
| Documentation | Windows setup, synopsis, architecture, technical design, cost, tests, demo and viva |

Implementation presence does not prove successful deployment. This update synchronizes source and documentation; the student's live Azure setup remains outstanding.

## Remaining completion phases

1. **Student subscription:** activate eligibility, select subscription/region, check quota/price and set spending controls.
2. **Deployment:** follow [Windows setup](setup-windows.md), create SSH key, preview Bicep and deploy a published release.
3. **Live integration:** verify cloud-init, identity role, storage privacy, HTTPS, registration, upload, previews and worker analysis.
4. **Persistence/recovery:** restart/deallocate/start; verify account/media persistence; export database/media backups and rehearse restore.
5. **Demonstration:** warm models, rehearse six synthetic images and guarded cleanup, capture screenshots and real CI evidence.
6. **Academic completion:** enter names/supervisor details, record actual contributions, costs and limitations, collect independent labeled measurements if making accuracy claims.

## Acceptance gates

- Required application/infrastructure checks pass for the chosen source/release; report unavailable checks separately.
- Original and thumbnail objects stay private; authorized previews resolve through expiring SAS.
- Two accounts cannot read or delete each other's media.
- Exact copies, verified near duplicates and semantic suggestions remain clearly distinguished.
- Confirmed deletion preserves the keeper and handles deferred object cleanup.
- Existing media receives version-6 analysis after smart-index upgrade.
- No credentials, personal uploads, model caches or generated dependency/build directories are committed.
- Website survives ordinary service/VM restart with persistent data.
- Remaining credit, daily shutdown and backup location are documented.

Optional course requirements should be rehearsed separately: Kubernetes scaling, Terraform plan/apply and Prometheus/Grafana apply to the local extension. They do not describe the five-container Azure deployment.

## Evidence and definition of done

Record actual commands/results in [validation-report.md](validation-report.md), deployment screenshots in the report/presentation and individual evidence in [contribution-template.md](contribution-template.md). The live goal is complete only when the selected Azure environment passes its integration checks; updating files alone does not meet that gate.