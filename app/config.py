"""All settings come from environment variables.

On Azure, Terraform sets them on the App Service (see infra/main.tf).
On your computer nothing needs to be set: ImageVault uses a SQLite file and a
local folder inside ./data, so you can run it without any cloud account.

  DATABASE_URL                           PostgreSQL connection (default: SQLite in ./data)
  AZURE_STORAGE_ACCOUNT_URL              Blob Storage account, accessed with the App Service's managed identity
  AZURE_STORAGE_CONNECTION_STRING        ...or a connection string (handy for local testing with Azurite)
  AZURE_STORAGE_CONTAINER                Blob container name (default: photos)
  APPLICATIONINSIGHTS_CONNECTION_STRING  Sends logs, requests and errors to Application Insights
  APP_PASSWORD                           Password that visitors must enter (leave empty to disable)
  IMAGEVAULT_AI                          Set to "off" to turn off the free AI (people, smart search, same subject)
  IMAGEVAULT_MODEL_DIR                   Where the AI models are kept (default: ./data/models)
  IMAGEVAULT_DATA_DIR                    Folder for local data (default: ./data)
"""

import os
from pathlib import Path

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per photo


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def data_dir() -> Path:
    path = Path(env("IMAGEVAULT_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_url() -> str:
    return env("DATABASE_URL") or f"sqlite:///{(data_dir() / 'imagevault.db').as_posix()}"


def running_on_azure() -> bool:
    return bool(env("WEBSITE_SITE_NAME"))  # set automatically by Azure App Service
