# Optional local development

The primary classroom path is [Azure](azure-students.md). Local development keeps
MinIO, Nginx and monitoring for offline work or course requirements.

## Docker

Install Docker with Compose. Copy `.env.example` to `.env` and replace every
placeholder password with an independently generated secret before starting.

```sh
docker compose up -d --build
docker compose ps
```

Open `http://localhost`. Downloaded release bundles can avoid rebuilding React:

```sh
docker compose -f docker-compose.yml -f docker-compose.download.yml up -d --build
```

The local monitoring URLs are configured in `.env.example`. Azure does not start
these monitoring containers. MinIO stores local objects; Azure Blob stores cloud
objects. Follow the migration instructions in [azure-students.md](azure-students.md)
when moving existing data. Database state must also be migrated; switching object
providers alone does not migrate metadata or accounts.

## Checks

Python 3.12:

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check app tests
pytest -q
```

Node 22:

```sh
cd frontend
npm ci
npm run lint
npm test
npm run build
```

Tests do not load the large CLIP model. The worker Dockerfile includes inference,
media and face-model dependencies. Rehearse detection on the deployed worker too.

The existing `infra/kubernetes`, `infra/terraform`, and `infra/monitoring` examples
are optional course extensions. They are not required by the Azure website.
