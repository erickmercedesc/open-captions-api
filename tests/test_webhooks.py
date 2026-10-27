from datetime import timedelta
from types import SimpleNamespace

from capservice.config import get_settings
from capservice.db import create_db_engine, session_factory
from capservice.repository import (
    create_job,
    mark_completed,
    mark_failed,
    schedule_webhook_retry,
)
from capservice.webhooks import retry_delay, webhook_payload
from capservice.worker import process_webhook, run_once


def test_webhook_payloads() -> None:
    completed = SimpleNamespace(id="job-1", status="completed", error=None)
    failed = SimpleNamespace(id="job-2", status="failed", error="The source video is invalid.")
    assert webhook_payload(completed, "https://caps.example.test/out.mp4") == {
        "job_id": "job-1",
        "status": "completed",
        "output_url": "https://caps.example.test/out.mp4",
    }
    assert webhook_payload(failed, None) == {
        "job_id": "job-2",
        "status": "failed",
        "error": "The source video is invalid.",
    }


def test_progressive_backoff(settings_env) -> None:
    settings = get_settings()
    assert retry_delay(settings, 1) == timedelta(seconds=1)
    assert retry_delay(settings, 2) == timedelta(seconds=2)
    assert retry_delay(settings, 3) == timedelta(seconds=4)


def test_webhook_retry_does_not_reprocess(settings_env, monkeypatch) -> None:
    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()
    render_calls: list[str] = []
    monkeypatch.setattr(
        "capservice.worker.render_captions_isolated",
        lambda *args, **kwargs: render_calls.append("render"),
    )
    monkeypatch.setattr("capservice.worker.deliver_webhook", lambda *args, **kwargs: False)

    try:
        job = create_job(
            session,
            video_url="https://example.com/video.mp4",
            webhook_url="https://example.com/hook",
            template="default",
        )
        mark_completed(session, job, output_token="token", retention_hours=24)
        process_attempts = job.process_attempts
        process_webhook(session, job, settings)
        session.refresh(job)
        assert job.status == "completed"
        assert job.webhook_status == "pending"
        assert job.webhook_attempts == 1
        assert job.next_webhook_at is not None
        assert job.process_attempts == process_attempts
        assert render_calls == []
    finally:
        session.close()


def test_failed_job_notifies_webhook(settings_env, monkeypatch) -> None:
    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()
    captured: list[dict] = []

    def fake_deliver(job, payload, _settings) -> bool:
        captured.append(payload)
        return True

    monkeypatch.setattr("capservice.worker.deliver_webhook", fake_deliver)
    try:
        job = create_job(
            session,
            video_url="https://example.com/video.mp4",
            webhook_url="https://example.com/hook",
            template="default",
        )
        mark_failed(session, job, "The source video is invalid.")
        assert run_once(session, settings) is True
        session.refresh(job)
        assert job.webhook_status == "delivered"
        assert captured == [
            {
                "job_id": job.id,
                "status": "failed",
                "error": "The source video is invalid.",
            }
        ]
    finally:
        session.close()


def test_webhook_exhausts_retries(settings_env) -> None:
    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()
    try:
        job = create_job(
            session,
            video_url="https://example.com/video.mp4",
            webhook_url="https://example.com/hook",
            template="default",
        )
        mark_completed(session, job, output_token="token", retention_hours=24)
        schedule_webhook_retry(session, job, delay=timedelta(seconds=1), exhausted=True)
        session.refresh(job)
        assert job.webhook_status == "failed"
        assert job.status == "completed"
    finally:
        session.close()
