# Cost analysis

> The original local deployment is described below. For Azure Blob/AWS S3, VM hosting, private access, migration and credit controls, see [cloud-deployment.md](cloud-deployment.md). Cloud mode stores media in your chosen provider and runs self-hosted AI on your laptop or VM.

The required demonstration uses existing student hardware and local free/open-source software. “₹0” means no additional software license, AI API, database, object-storage, monitoring, or public-cloud bill. It does not claim that laptop hardware, electricity, or internet access are literally free.

| Component | Product | Required project expenditure |
|---|---|---:|
| Frontend | React, TypeScript, Vite, Tailwind CSS | ₹0 |
| Backend | FastAPI, SQLAlchemy, Alembic | ₹0 |
| Authentication | Argon2 + JWT in the self-hosted API | ₹0 |
| AI model | OpenCLIP ViT-B/32, local inference | ₹0 |
| Image processing | Pillow, ImageHash | ₹0 |
| Database | PostgreSQL | ₹0 |
| Vector search | pgvector | ₹0 |
| Object storage | MinIO | ₹0 |
| Job queue | Redis + Celery | ₹0 |
| Containers | Docker / Docker Compose | ₹0 for the required local project setup |
| Orchestration | Kubernetes + Minikube | ₹0 |
| Infrastructure as Code | Terraform | ₹0 |
| CI/CD | GitHub Actions within applicable free/public-repository usage | ₹0 for the project setup |
| Metrics | Prometheus | ₹0 |
| Visualization | Grafana OSS | ₹0 |
| Reverse proxy | Nginx | ₹0 |
| Required demo hosting | Existing student laptop | ₹0 additional cloud bill |
| **Total software/cloud-service cost** |  | **₹0** |

Optional conceptual AWS/Azure/GCP mappings are not deployed and are not included in the project’s required path. A future public-cloud migration would introduce usage-based charges and require a separate budget.
