from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from capservice.db import UTC, Job, utcnow


def create_job(session: Session, *, video_url: str, webhook_url: str, template: str) -> Job:
    now = utcnow()
    job = Job(
        id=str(uuid4()),
        status="queued",
        video_url=video_url,
        webhook_url=webhook_url,
        template=template,
        process_attempts=0,
        webhook_status="pending",
        webhook_attempts=0,
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job(session: Session, job_id: str) -> Job | None:
    return session.get(Job, job_id)


def claim_next_queued_job(session: Session, *, max_concurrent: int) -> Job | None:
    now = utcnow()
    result = session.execute(
        text(
            """
            UPDATE jobs
            SET status = 'processing',
                started_at = :now,
                heartbeat_at = :now,
                updated_at = :now,
                process_attempts = process_attempts + 1
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
            )
            AND (SELECT COUNT(*) FROM jobs WHERE status = 'processing') < :max_concurrent
            RETURNING id
            """
        ),
        {"now": now, "max_concurrent": max_concurrent},
    )
    row = result.fetchone()
    session.commit()
    if row is None:
        return None
    return session.get(Job, row[0])


def heartbeat(session: Session, job: Job) -> None:
    job.heartbeat_at = utcnow()
    job.updated_at = job.heartbeat_at
    session.commit()


def mark_completed(
    session: Session,
    job: Job,
    *,
    output_token: str,
    retention_hours: float,
) -> None:
    now = utcnow()
    job.status = "completed"
    job.output_token = output_token
    job.error = None
    job.finished_at = now
    job.updated_at = now
    job.expires_at = now + timedelta(hours=retention_hours)
    job.webhook_status = "pending"
    job.next_webhook_at = now
    session.commit()


def mark_failed(session: Session, job: Job, public_error: str) -> None:
    now = utcnow()
    job.status = "failed"
    job.error = public_error
    job.finished_at = now
    job.updated_at = now
    job.webhook_status = "pending"
    job.next_webhook_at = now
    session.commit()


def recover_stale_webhooks(session: Session, *, stale_after: timedelta) -> None:
    now = utcnow()
    jobs = session.scalars(select(Job).where(Job.webhook_status == "delivering")).all()
    for job in jobs:
        reference = job.updated_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        if now - reference < stale_after:
            continue
        job.webhook_status = "pending"
        job.next_webhook_at = now
        job.updated_at = now
    session.commit()


def recover_stale_jobs(
    session: Session,
    *,
    stale_after: timedelta,
    max_attempts: int,
) -> list[Job]:
    now = utcnow()
    stale: list[Job] = []
    jobs = session.scalars(select(Job).where(Job.status == "processing")).all()
    for job in jobs:
        reference = job.heartbeat_at or job.started_at or job.updated_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        if now - reference < stale_after:
            continue
        if job.process_attempts < max_attempts:
            job.status = "queued"
            job.started_at = None
            job.heartbeat_at = None
        else:
            job.status = "failed"
            job.error = "Processing timed out."
            job.finished_at = now
            job.webhook_status = "pending"
            job.next_webhook_at = now
        job.updated_at = now
        stale.append(job)
    session.commit()
    return stale


def claim_webhook_job(session: Session) -> Job | None:
    now = utcnow()
    result = session.execute(
        text(
            """
            UPDATE jobs
            SET webhook_status = 'delivering',
                updated_at = :now
            WHERE id = (
                SELECT id FROM jobs
                WHERE status IN ('completed', 'failed')
                  AND webhook_status = 'pending'
                  AND next_webhook_at IS NOT NULL
                  AND next_webhook_at <= :now
                ORDER BY next_webhook_at ASC
                LIMIT 1
            )
            AND webhook_status = 'pending'
            RETURNING id
            """
        ),
        {"now": now},
    )
    row = result.fetchone()
    session.commit()
    if row is None:
        return None
    return session.get(Job, row[0])


def mark_webhook_delivered(session: Session, job: Job) -> None:
    job.webhook_status = "delivered"
    job.webhook_attempts += 1
    job.next_webhook_at = None
    job.updated_at = utcnow()
    session.commit()


def schedule_webhook_retry(
    session: Session,
    job: Job,
    *,
    delay: timedelta,
    exhausted: bool,
) -> None:
    now = utcnow()
    job.webhook_attempts += 1
    job.updated_at = now
    if exhausted:
        job.webhook_status = "failed"
        job.next_webhook_at = None
    else:
        job.webhook_status = "pending"
        job.next_webhook_at = now + delay
    session.commit()


def expired_jobs(session: Session, now: datetime | None = None) -> list[Job]:
    now = now or utcnow()
    return list(
        session.scalars(
            select(Job).where(
                Job.status == "completed",
                Job.expires_at.is_not(None),
                Job.expires_at <= now,
            )
        )
    )
