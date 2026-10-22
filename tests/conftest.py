import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# The AI models (about 190 MB) are downloaded once and shared by all test runs.
MODEL_DIR = os.environ.get("TEST_MODEL_DIR") or str(Path(__file__).resolve().parent.parent / "data" / "models")


@pytest.fixture(scope="session")
def ai_models():
    """Download the AI models once for the whole test run."""
    from app import ai

    previous = os.environ.get("IMAGEVAULT_MODEL_DIR")
    os.environ["IMAGEVAULT_MODEL_DIR"] = MODEL_DIR
    try:
        ai.download_models()
    finally:
        if previous is None:
            os.environ.pop("IMAGEVAULT_MODEL_DIR")
        else:
            os.environ["IMAGEVAULT_MODEL_DIR"] = previous


@pytest.fixture
def client(tmp_path, monkeypatch):
    """By default tests use SQLite and a local folder. CI also runs them against PostgreSQL and
    Azurite (the Azure Storage emulator) by setting TEST_DATABASE_URL and TEST_AZURE_STORAGE."""
    monkeypatch.setenv("IMAGEVAULT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("IMAGEVAULT_MODEL_DIR", MODEL_DIR)
    monkeypatch.delenv("IMAGEVAULT_AI", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", ""))
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", os.environ.get("TEST_AZURE_STORAGE", ""))
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER", f"test-{uuid.uuid4().hex[:12]}")
    from app.database import engine, init_db, metadata
    from app.server import app

    metadata.drop_all(engine())
    init_db()
    return TestClient(app)  # used without "with", so the background AI worker does not start
