from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from capservice.config import reset_settings


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key-123456")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://caps.example.test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WEBHOOK_BACKOFF_BASE_SECONDS", "1")
    monkeypatch.setenv("WORKER_POLL_SECONDS", "0.01")
    monkeypatch.setenv("OUTPUT_RETENTION_HOURS", "24")
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": "test-key-123456"}


@pytest.fixture
def client(settings_env):
    from capservice.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
