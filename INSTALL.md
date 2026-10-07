# Deploy the ImageVault website

Visitors use the deployed HTTPS website in a browser. They do not need a desktop
app, Docker, a download, or an Azure account. Ask the website owner for an invitation
code to register, then upload and manage photos on the site.

## Host your own website on Azure for Students

If you already have this repository folder on Windows, follow
[Windows setup](docs/setup-windows.md). You do not need to clone it again or
install Docker on your laptop to deploy to Azure.

Download **imagevault-ai.zip** or **imagevault-ai.tar.gz** from
[GitHub Releases](https://github.com/Arnav-Dugad/imagevault-ai/releases/latest).
Each bundle includes the website source, compiled frontend, Python server and
AI worker, Docker definitions, Azure deployment scripts, documentation and license.
Follow [the Azure for Students guide](docs/azure-students.md) to deploy it.

You need your own verified student subscription and enough regional VM quota.
Keep the spending limit enabled: the default AI-capable VM uses student credit.
The compiled frontend cannot store or analyze photos without the API and worker;
deploy the full stack, rather than uploading only the HTML to static hosting.

## Local development or demonstration

The original Docker Compose and PowerShell development scripts remain supported.
See [local development](docs/local-development.md) and
[Windows setup](docs/setup-windows.md#optional-run-on-this-windows-pc). Downloaded bundles can
use `docker-compose.download.yml` after the local Compose file to serve the
already-built frontend, avoiding a Node build:

```bash
docker compose -f docker-compose.yml -f docker-compose.download.yml up -d --build
```

Configure a private `.env` first as described in the local development guide. This starts a local
website at <http://localhost>; it does not install a desktop application.

## Verify downloads

Run `sha256sum --check --ignore-missing SHA256SUMS` beside the downloaded archive.
Alternatively, hash the archive with your OS's SHA-256 utility and compare it with
the corresponding entry in **SHA256SUMS** from the same GitHub release.

## Updates and data

Back up PostgreSQL and the object store before upgrading. Extract the next bundle
into the existing installation directory, retain the private `.env` and Docker
volumes, and rebuild/start the relevant Compose stack. Database migrations run
at API startup. Avoid `docker compose down -v` unless deleting local data is intended.
See the Azure guide for cloud updates, shutdown, migration and backup instructions.
