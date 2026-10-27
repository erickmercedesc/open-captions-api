from pathlib import Path

from capservice.config import get_settings
from capservice.db import create_db_engine, session_factory
from capservice.errors import PublicError
from capservice.repository import create_job
from capservice.worker import process_job, run_once


def test_processes_one_job_and_stores_output(settings_env, monkeypatch, tmp_path) -> None:
    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()

    def fake_download(url, destination: Path, **_kwargs) -> None:
        destination.write_bytes(b"source-video")

    def fake_render(input_path: Path, output_path: Path, **_kwargs) -> None:
        output_path.write_bytes(b"rendered-video")

    monkeypatch.setattr("capservice.worker.download_video", fake_download)
    monkeypatch.setattr("capservice.worker.validate_source_video", lambda *args, **kwargs: None)
    monkeypatch.setattr("capservice.worker.render_captions_isolated", fake_render)
    monkeypatch.setattr("capservice.worker.validate_output_video", lambda *args, **kwargs: None)
    monkeypatch.setattr("capservice.worker.deliver_webhook", lambda *args, **kwargs: True)

    try:
        job = create_job(
            session,
            video_url="https://example.com/video.mp4",
            webhook_url="https://example.com/hook",
            template="minimalist",
        )
        assert run_once(session, settings) is True
        session.refresh(job)
        assert job.status == "completed"
        assert job.output_token
        output = settings.outputs_dir / f"{job.id}-{job.output_token}.mp4"
        assert output.is_file()
        assert list(settings.tmp_dir.iterdir()) == []
        assert run_once(session, settings) is True
        session.refresh(job)
        assert job.webhook_status == "delivered"
    finally:
        session.close()


def test_processing_error_marks_failed(settings_env, monkeypatch) -> None:
    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()
    monkeypatch.setattr(
        "capservice.worker.download_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(PublicError("The video could not be downloaded.")),
    )
    try:
        job = create_job(
            session,
            video_url="https://example.com/video.mp4",
            webhook_url="https://example.com/hook",
            template="default",
        )
        process_job(session, job, settings)
        session.refresh(job)
        assert job.status == "failed"
        assert job.error == "The video could not be downloaded."
        assert job.webhook_status == "pending"
    finally:
        session.close()


def test_single_concurrency_skips_when_busy(settings_env) -> None:
    settings = get_settings()
    session = session_factory(create_db_engine(settings.db_path))()
    try:
        first = create_job(
            session,
            video_url="https://example.com/one.mp4",
            webhook_url="https://example.com/hook",
            template="default",
        )
        second = create_job(
            session,
            video_url="https://example.com/two.mp4",
            webhook_url="https://example.com/hook",
            template="default",
        )
        from capservice.repository import claim_next_queued_job

        claimed = claim_next_queued_job(session, max_concurrent=1)
        skipped = claim_next_queued_job(session, max_concurrent=1)
        assert claimed is not None
        assert claimed.id == first.id
        assert skipped is None
        session.refresh(second)
        assert second.status == "queued"
    finally:
        session.close()
