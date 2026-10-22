"""Where ImageVault keeps its files, and the user's saved settings.

Everything lives in one data folder:
  imagevault.db   - the SQLite database (photo list, hashes, duplicate matches)
  photos/         - original photos (when using local storage)
  thumbs/         - small preview images
  settings.json   - saved settings, such as the Azure connection string

Environment variables override the saved settings. They are mainly useful when
ImageVault runs as a website on Azure App Service (see docs/azure.md).
"""

import json
import os
import sys
from pathlib import Path

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per photo


def data_dir() -> Path:
    if custom := os.environ.get("IMAGEVAULT_DATA_DIR"):
        path = Path(custom)
    elif sys.platform == "win32":
        path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ImageVault"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "ImageVault"
    else:
        path = Path.home() / ".local" / "share" / "imagevault"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_file() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(_settings_file().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_settings(settings: dict) -> None:
    _settings_file().write_text(json.dumps(settings, indent=2), encoding="utf-8")


def azure_settings() -> tuple[str, str, bool]:
    """Return (connection_string, container, set_by_environment)."""
    env_value = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if env_value:
        return env_value, os.environ.get("AZURE_STORAGE_CONTAINER", "photos"), True
    saved = load_settings()
    return saved.get("azure_connection_string", ""), saved.get("azure_container", "photos"), False


def app_password() -> str:
    """Optional password. Set APP_PASSWORD when the app is hosted on the internet."""
    return os.environ.get("APP_PASSWORD", "")
