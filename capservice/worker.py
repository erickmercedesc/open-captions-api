from __future__ import annotations

import signal
import sys
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from capservice.captions import render_captions_isolated
from capservice.config import Settings, get_settings
from capservice.db import Job, create_db_engine, session_factory, utcnow
from capservice.download import download_video
from capservice.errors import PublicError
from capservice.log import configure_logging, get_logger
from capservice.media import require_ffmpeg, validate_output_video, validate_source_video
from capservice.repository import (
    claim_next_queued_job,
    claim_webhook_job,
    expired_jobs,
    heartbeat,
    mark_completed,
    mark_failed,
    mark_webhook_delivered,
    recover_stale_jobs,
    recover_stale_webhooks,
    schedule_webhook_retry,
)
from capservice.storage import (
    cleanup_job_tmp,
    delete_if_exists,
    job_tmp_dir,
    new_output_token,
    output_path,
    public_output_url,
    store_output,
)
from capservice.webhooks import deliver_webhook, retry_delay, webhook_payload

logger = get_logger(__name__)
_RUNNING = True


def _handle_stop(signum: int, _frame: object) -> None:
    global _RUNNING
    logger.info("worker_stop_signal", signal=signum)
    _RUNNING = False


def process_job(session: Session, job: Job, settings: Settings) -> None:
    heartbeat(session, job)
    tmp = job_tmp_dir(settings, job.id)
    source = tmp / "source.mp4"
    rendered = tmp / "captions.mp4"
    try:
        logger.info("job_download", job_id=job.id)
        download_video(
            job.video_url,
            source,
            max_bytes=settings.max_video_bytes,
            timeout_seconds=settings.download_timeout_seconds,
        )
        heartbeat(session, job)
        validate_source_video(
            source,
            max_bytes=settings.max_video_bytes,
            max_duration_seconds=settings.max_video_duration_seconds,
        )
        heartbeat(session, job)
        logger.info("job_render", job_id=job.id, template=job.template)
        render_captions_isolated(
            source,
            rendered,
            template=job.template,
            language=settings.whisper_language,
            model_size=settings.whisper_model,
            backend=settings.whisper_backend,
            default_template=settings.default_template,
            timeout_seconds=settings.processing_timeout_seconds,
        )
        heartbeat(session, job)
        validate_output_video(rendered)
        token = new_output_token()
        job.output_token = token
        store_output(settings, job, rendered)
        mark_completed(session, job, output_token=token, retention_hours=settings.output_retention_hours)
        logger.info("job_completed", job_id=job.id)
    except PublicError as exc:
        logger.warning("job_failed", job_id=job.id, error=exc.public_message)
        mark_failed(session, job, exc.public_message)
    except Exception:
        logger.exception("job_failed_internal", job_id=job.id)
        mark_failed(session, job, "Caption generation failed.")
    finally:
        delete_if_exists(source)
        delete_if_exists(rendered)
        cleanup_job_tmp(settings, job.id)


def process_webhook(session: Session, job: Job, settings: Settings) -> None:
    output_url = None
    if job.status == "completed" and job.output_token:
        path = output_path(settings, job)
        if path.is_file():
            output_url = public_output_url(settings, job)
    payload = webhook_payload(job, output_url)
    try:
        ok = deliver_webhook(job, payload, settings)
    except Exception:
        logger.exception("webhook_delivery_error", job_id=job.id)
        ok = False
    if ok:
        mark_webhook_delivered(session, job)
        return
    attempts_after = job.webhook_attempts + 1
    exhausted = attempts_after >= settings.webhook_max_attempts
    schedule_webhook_retry(
        session,
        job,
        delay=retry_delay(settings, attempts_after),
        exhausted=exhausted,
    )
    logger.warning(
        "webhook_scheduled_retry",
        job_id=job.id,
        attempts=attempts_after,
        exhausted=exhausted,
    )


def cleanup_expired_outputs(session: Session, settings: Settings) -> None:
    for job in expired_jobs(session):
        path = Path(settings.outputs_dir / f"{job.id}-{job.output_token}.mp4") if job.output_token else None
        if path:
            delete_if_exists(path)
        job.output_token = None
        job.updated_at = utcnow()
        session.commit()
        logger.info("output_expired", job_id=job.id)


def run_once(session: Session, settings: Settings) -> bool:
    recover_stale_jobs(
        session,
        stale_after=timedelta(seconds=settings.stale_processing_seconds),
        max_attempts=settings.max_process_attempts,
    )
    recover_stale_webhooks(session, stale_after=timedelta(seconds=60))
    cleanup_expired_outputs(session, settings)

    job = claim_next_queued_job(session, max_concurrent=settings.max_concurrent_jobs)
    if job is not None:
        process_job(session, job, settings)
        return True

    webhook_job = claim_webhook_job(session)
    if webhook_job is not None:
        process_webhook(session, webhook_job, settings)
        return True
    return False


def run_worker(settings: Settings | None = None) -> None:
    configure_logging()
    settings = settings or get_settings()
    require_ffmpeg()
    engine = create_db_engine(settings.db_path)
    factory = session_factory(engine)
    logger.info("worker_started", db=str(settings.db_path))
    with factory() as session:
        while _RUNNING:
            try:
                did_work = run_once(session, settings)
            except Exception:
                logger.exception("worker_loop_error")
                did_work = False
            if not did_work:
                time.sleep(settings.worker_poll_seconds)


def main() -> None:
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    run_worker()


if __name__ == "__main__":
    main()
    sys.exit(0)
