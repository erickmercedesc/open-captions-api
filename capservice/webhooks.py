from __future__ import annotations

from datetime import timedelta

import httpx

from capservice.config import Settings
from capservice.db import Job
from capservice.log import get_logger
from capservice.ssrf import validate_public_https_url

logger = get_logger(__name__)


def webhook_payload(job: Job, output_url: str | None) -> dict[str, str]:
    if job.status == "completed" and output_url:
        return {"job_id": job.id, "status": "completed", "output_url": output_url}
    return {
        "job_id": job.id,
        "status": "failed",
        "error": job.error or "Caption generation failed.",
    }


def deliver_webhook(job: Job, payload: dict[str, str], settings: Settings) -> bool:
    url = validate_public_https_url(job.webhook_url)
    timeout = httpx.Timeout(settings.webhook_timeout_seconds)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = client.post(url, json=payload)
    except httpx.HTTPError:
        logger.warning("webhook_network_error", job_id=job.id)
        return False

    if 200 <= response.status_code < 300:
        logger.info("webhook_delivered", job_id=job.id, attempt=job.webhook_attempts + 1)
        return True
    if response.status_code == 429 or 500 <= response.status_code <= 599:
        logger.warning("webhook_retryable", job_id=job.id, status_code=response.status_code)
        return False
    logger.warning("webhook_rejected", job_id=job.id, status_code=response.status_code)
    return False


def retry_delay(settings: Settings, attempts_after_this: int) -> timedelta:
    exponent = max(attempts_after_this - 1, 0)
    seconds = settings.webhook_backoff_base_seconds * (2**exponent)
    return timedelta(seconds=seconds)
