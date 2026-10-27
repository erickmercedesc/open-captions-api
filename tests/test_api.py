from capservice.config import get_settings
from capservice.db import create_db_engine, session_factory
from capservice.repository import get_job


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_requires_api_key(client) -> None:
    response = client.post(
        "/generate-captions",
        json={
            "video_url": "https://example.com/video.mp4",
            "webhook_url": "https://example.com/hook",
        },
    )
    assert response.status_code == 401


def test_rejects_private_webhook(client, auth_headers) -> None:
    response = client.post(
        "/generate-captions",
        json={
            "video_url": "https://example.com/video.mp4",
            "webhook_url": "https://127.0.0.1/hook",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_rejects_unknown_template(client, auth_headers) -> None:
    response = client.post(
        "/generate-captions",
        json={
            "video_url": "https://example.com/video.mp4",
            "webhook_url": "https://example.com/hook",
            "template": "does-not-exist",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_enqueue_returns_202(client, auth_headers) -> None:
    response = client.post(
        "/generate-captions",
        json={
            "video_url": "https://example.com/video.mp4",
            "webhook_url": "https://example.com/hook",
            "template": "minimalist",
        },
        headers=auth_headers,
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]

    job_response = client.get(f"/jobs/{body['job_id']}", headers=auth_headers)
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "queued"
    assert job_response.json()["template"] == "minimalist"


def test_http_restart_keeps_queued_jobs(client, auth_headers, settings_env) -> None:
    response = client.post(
        "/generate-captions",
        json={
            "video_url": "https://example.com/clip.mp4",
            "webhook_url": "https://example.com/hook",
        },
        headers=auth_headers,
    )
    job_id = response.json()["job_id"]

    from fastapi.testclient import TestClient
    from capservice.main import create_app

    with TestClient(create_app()) as restarted:
        body = restarted.get(f"/jobs/{job_id}", headers=auth_headers).json()
        assert body["status"] == "queued"

    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()
    try:
        job = get_job(session, job_id)
        assert job is not None
        assert job.status == "queued"
    finally:
        session.close()
